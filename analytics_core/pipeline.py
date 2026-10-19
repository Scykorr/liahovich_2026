from __future__ import annotations

import platform
from collections.abc import Callable
from itertools import combinations
from typing import Any

from analytics_core.runtime import configure_threads, thread_mode

configure_threads()

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import sklearn  # noqa: E402
from scipy import __version__ as scipy_version  # noqa: E402
from statsmodels import __version__ as statsmodels_version  # noqa: E402

from analytics_core.clustering import fit_cluster_model
from analytics_core.exceptions import DivisionByZeroError, PipelineError
from analytics_core.features import combo_diagnostics, correlation_screen, drop_low_information, iterative_vif
from analytics_core.formulas import (
    candidate_share,
    fixed_leader_key,
    invalid_share,
    leader_margin,
    opposition_sum,
    outside_share,
    turnout,
)
from analytics_core.ranking import apply_internal_ranks, apply_total_scores, internal_sort_key, recommend_index
from analytics_core.stability import repeated_subsample_stability
from analytics_core.types import (
    CandidateResult,
    DroppedFeature,
    PipelineConfig,
    PipelineResult,
    PrecinctRow,
)

ProgressCallback = Callable[[int, str], None]

SYNTHETIC_FEATURES = [
    "turnout",
    "outside",
    "invalid",
    "candidate_B",
    "candidate_C",
    "candidate_D",
]


def library_versions() -> dict[str, str]:
    import numpy
    import pandas

    return {
        "python": platform.python_version(),
        "numpy": numpy.__version__,
        "pandas": pandas.__version__,
        "scipy": scipy_version,
        "scikit-learn": sklearn.__version__,
        "statsmodels": statsmodels_version,
        "kmeans_algorithm": "lloyd",
        "kmeans_init": "k-means++",
        "threads": str(thread_mode()),
    }


def synthetic_control_config(**overrides: Any) -> PipelineConfig:
    """Конфигурация автономного синтетического опыта: 22 подмножества, top-5 подвыборок."""
    config = PipelineConfig(
        seed=20261019,
        feature_screen_mode="diagnostic",
        min_unique=2,
        scaler="standard",
        n_init=20,
        k_min=2,
        k_max=6,
        feature_combo_min=2,
        feature_combo_max=4,
        min_cluster_share=0.05,
        subsample_repeats=100,
        subsample_fraction=0.80,
        subsample_top_n=5,
        silhouette_max_rows=0,
        selected_features=list(SYNTHETIC_FEATURES),
        combo_must_include=["turnout"],
        combo_must_include_any=["candidate_B", "candidate_C", "candidate_D"],
    )
    for key, value in overrides.items():
        setattr(config, key, value)
    return config


def fixed_leader_name(rows: list[PrecinctRow]) -> str:
    totals: dict[str, float] = {}
    for row in rows:
        for name, votes in row.candidate_votes.items():
            totals[name] = totals.get(name, 0.0) + float(votes)
    if not totals:
        return ""
    return fixed_leader_key(totals)


def build_feature_frame(rows: list[PrecinctRow], leader_key: str | None = None) -> pd.DataFrame:
    leader = leader_key if leader_key is not None else fixed_leader_name(rows)
    records: list[dict[str, Any]] = []
    for row in rows:
        if row.registered_voters == 0 or row.ballots_in_boxes == 0 or row.valid_ballots == 0:
            raise DivisionByZeroError(
                f"Строка {row.row_number}: нулевой знаменатель, расчёт признаков невозможен"
            )
        shares = {name: candidate_share(votes, row.valid_ballots) for name, votes in row.candidate_votes.items()}
        record: dict[str, Any] = {
            "precinct_id": f"{row.territory_code}:{row.precinct_code}",
            "territory_code": row.territory_code,
            "precinct_code": row.precinct_code,
            "row_number": row.row_number,
            "turnout": turnout(row.ballots_in_boxes, row.registered_voters),
            "outside": outside_share(row.outside_ballots, row.ballots_in_boxes),
            "invalid": invalid_share(row.invalid_ballots, row.ballots_in_boxes),
            "opposition_sum": opposition_sum(shares, leader) if shares and leader else 0.0,
            "leader_margin": leader_margin(shares, leader) if shares and leader else 0.0,
        }
        record.update(shares)
        records.append(record)
    return pd.DataFrame.from_records(records)


def feature_combos(features: list[str], config: PipelineConfig) -> list[list[str]]:
    if not features:
        return []
    combo_min = config.feature_combo_min
    combo_max = min(config.feature_combo_max, len(features))
    if combo_min > combo_max:
        return []
    combos: list[list[str]] = []
    for size in range(combo_min, combo_max + 1):
        for combo in combinations(features, size):
            names = list(combo)
            if config.combo_must_include and any(name not in names for name in config.combo_must_include):
                continue
            if config.combo_must_include_any and not any(name in names for name in config.combo_must_include_any):
                continue
            combos.append(names)
    return combos


def mark_outliers(df: pd.DataFrame, feature_cols: list[str], zscore: float) -> list[str]:
    if not feature_cols or df.empty:
        return []
    matrix = df[feature_cols].astype(float)
    std = matrix.std(ddof=0).replace(0, np.nan)
    z = ((matrix - matrix.mean()) / std).abs()
    mask = (z > zscore).any(axis=1)
    return df.loc[mask, "precinct_id"].tolist()


def run_pipeline(
    rows: list[PrecinctRow],
    config: PipelineConfig,
    progress: ProgressCallback | None = None,
    cancelled: Callable[[], bool] | None = None,
) -> PipelineResult:
    def _progress(percent: int, message: str) -> None:
        if cancelled and cancelled():
            raise PipelineError("Запуск отменён")
        if progress:
            progress(percent, message)

    _progress(5, "Загрузка и расчёт признаков")
    if not rows:
        raise PipelineError("Нет строк для анализа")

    leader = fixed_leader_name(rows)
    frame = build_feature_frame(rows, leader)
    n_input = len(frame)
    excluded_ids: list[str] = []
    feature_pool = ["turnout", "outside", "invalid"]
    candidate_cols = [
        col
        for col in frame.columns
        if col
        not in {
            "precinct_id",
            "territory_code",
            "precinct_code",
            "row_number",
            "opposition_sum",
            "leader_margin",
        }
        and col not in feature_pool
    ]
    feature_pool.extend(sorted(candidate_cols))
    if config.selected_features:
        missing = [name for name in config.selected_features if name not in frame.columns]
        if missing:
            raise PipelineError(f"Неизвестные признаки: {', '.join(missing)}")
        feature_pool = list(config.selected_features)

    _progress(12, "Отбор информативных признаков")
    working = frame[feature_pool].astype(float)
    working, dropped_low = drop_low_information(working, config.min_unique, config.min_variance)
    dropped: list[DroppedFeature] = list(dropped_low)
    warnings = [
        f"Фиксированный лидер массива: {leader or 'не определён'}. Доля «остальных» считается от него на каждом участке."
    ]
    if config.feature_screen_mode == "strict":
        _progress(18, "Строгий корреляционный экран")
        working, dropped_corr = correlation_screen(working, config.corr_threshold, min_keep=config.feature_combo_min)
        _progress(24, "Строгий итеративный VIF")
        working, dropped_vif, _vifs = iterative_vif(working, config.vif_threshold, min_keep=config.feature_combo_min)
        dropped.extend(dropped_corr)
        dropped.extend(dropped_vif)
        warnings.append("Строгий режим: корреляция и VIF удаляют признаки до перебора комбинаций.")
    else:
        warnings.append(
            "Диагностический режим: корреляция и VIF считаются для каждой комбинации и не удаляют признаки заранее."
        )
    features = list(working.columns)
    combos = feature_combos(features, config)
    if not combos:
        raise PipelineError(
            f"После отбора осталось {len(features)} признаков, подходящих комбинаций нет "
            f"(минимум {config.feature_combo_min})"
        )

    outlier_ids = mark_outliers(frame, features, config.outlier_zscore)
    used = frame.copy()
    n_excluded = len(excluded_ids)
    n_used = len(used)
    if n_used < max(10, config.k_max + 1):
        raise PipelineError(f"Недостаточно строк для кластеризации: {n_used}")

    k_values = list(range(config.k_min, config.k_max + 1))
    total_models = max(1, len(combos) * len(k_values))
    candidates: list[CandidateResult] = []

    _progress(30, "Перебор моделей")
    X_full = used[features].to_numpy(dtype=float)
    territories = used["territory_code"].to_numpy()
    precinct_ids = used["precinct_id"].tolist()

    done = 0
    for combo in combos:
        notes, reject_reason = combo_diagnostics(
            used,
            combo,
            corr_threshold=config.corr_threshold,
            vif_threshold=config.vif_threshold,
        )
        cols_idx = [features.index(name) for name in combo]
        X = X_full[:, cols_idx]
        for k in k_values:
            done += 1
            percent = 30 + int(40 * done / total_models)
            _progress(percent, f"Модель {done}/{total_models}: k={k}, признаки={combo}")
            if reject_reason:
                candidates.append(
                    CandidateResult(
                        features=list(combo),
                        k=k,
                        scaler=config.scaler,
                        silhouette=None,
                        calinski_harabasz=None,
                        davies_bouldin=None,
                        min_cluster_share=0.0,
                        rejected=True,
                        reject_reason=reject_reason,
                        diagnostics=list(notes),
                        n_used=n_used,
                        n_excluded=n_excluded,
                        precinct_ids=list(precinct_ids),
                    )
                )
                continue
            fitted = fit_cluster_model(
                X,
                k=k,
                scaler=config.scaler,
                seed=config.seed,
                n_init=config.n_init,
                silhouette_max_rows=config.silhouette_max_rows,
            )
            share = fitted["min_cluster_share"]
            rejected = share < config.min_cluster_share
            reason = ""
            if rejected:
                reason = f"Доля минимального кластера {share:.3f} < {config.min_cluster_share}"
            elif fitted["silhouette"] is None:
                rejected = True
                reason = "Не удалось рассчитать внутренние метрики"
            labels = fitted["labels"]
            sizes = {int(cluster): int(count) for cluster, count in zip(*np.unique(labels, return_counts=True), strict=False)}
            centers = {}
            raw_centers = _inverse_centers(fitted["pipeline"], combo)
            for cluster_id, center in enumerate(raw_centers):
                centers[int(cluster_id)] = {name: float(value) for name, value in zip(combo, center, strict=True)}
            boxplot = _boxplot_payload(X, combo, labels)
            tik_distribution = _tik_distribution(territories, labels)
            samples = fitted["silhouette_samples"]
            candidates.append(
                CandidateResult(
                    features=list(combo),
                    k=k,
                    scaler=config.scaler,
                    silhouette=fitted["silhouette"],
                    calinski_harabasz=fitted["calinski_harabasz"],
                    davies_bouldin=fitted["davies_bouldin"],
                    min_cluster_share=share,
                    rejected=rejected,
                    reject_reason=reason,
                    diagnostics=list(notes),
                    silhouette_rows=int(fitted["silhouette_rows"]),
                    n_used=n_used,
                    n_excluded=n_excluded,
                    labels=labels.tolist(),
                    distances=fitted["distances"].tolist(),
                    precinct_ids=list(precinct_ids),
                    centers=centers,
                    sizes=sizes,
                    boxplot=boxplot,
                    silhouette_samples=samples.tolist() if len(samples) else [],
                    tik_distribution=tik_distribution,
                    feature_matrix=X.tolist(),
                )
            )

    apply_internal_ranks(
        candidates,
        sil_weight=config.sil_weight,
        ch_weight=config.ch_weight,
        db_weight=config.db_weight,
    )
    eligible = [item for item in candidates if not item.rejected and item.internal_score is not None]
    eligible.sort(key=internal_sort_key)
    top = eligible[: config.subsample_top_n] if config.subsample_repeats > 0 else []
    _progress(75, "Устойчивость лучших кандидатов: стратифицированная подвыборка")
    for index, item in enumerate(top, start=1):
        _progress(75 + int(20 * index / max(len(top), 1)), f"Подвыборка {index}/{len(top)}")
        cols_idx = [features.index(name) for name in item.features]
        report = repeated_subsample_stability(
            X=X_full[:, cols_idx],
            territories=territories,
            reference_labels=np.asarray(item.labels),
            k=item.k,
            scaler=config.scaler,  # type: ignore[arg-type]
            seed=config.seed,
            n_init=config.n_init,
            repeats=config.subsample_repeats,
            fraction=config.subsample_fraction,
            column_positions=cols_idx,
        )
        item.ari_mean = report.ari_mean
        item.ari_p10 = report.ari_p10
        item.ari_p90 = report.ari_p90
        item.ari_sd = report.ari_sd
        item.stability_successes = report.successes
        item.stability_repeats = report.repeats
        item.stability_indices = report.indices
    apply_total_scores(
        candidates,
        internal_weight=config.internal_weight,
        ari_weight=config.ari_weight,
    )
    recommended = recommend_index(
        candidates,
        config.simplicity_delta,
        ari_mean_min=config.stability_ari_mean_min,
        ari_p10_min=config.stability_ari_p10_min,
    )
    admissible = [item for item in candidates if not item.rejected]
    checked = [item for item in candidates if item.ari_mean is not None]
    passed = [item for item in candidates if item.passes_stability]
    _progress(100, "Готово")
    if outlier_ids:
        warnings.append(
            f"Помечено выбросов: {len(outlier_ids)}. Они не исключаются из расчёта при правиле mark_only."
        )
    warnings.append(
        "Повторные оценки — стратифицированная подвыборка без возвращения, не bootstrap. "
        f"Рассчитано моделей: {len(candidates)}; допущено: {len(admissible)}; "
        f"с проверкой устойчивости: {len(checked)}; прошли порог устойчивости: {len(passed)}."
    )
    return PipelineResult(
        config=config,
        n_input=n_input,
        n_used=n_used,
        n_excluded=n_excluded,
        excluded_ids=excluded_ids,
        outlier_ids=outlier_ids,
        feature_columns=features,
        dropped_features=dropped,
        candidates=candidates,
        recommended_index=recommended,
        library_versions=library_versions(),
        fixed_leader=leader,
        models_calculated=len(candidates),
        models_admissible=len(admissible),
        models_stability_checked=len(checked),
        models_stability_passed=len(passed),
        warnings=warnings,
    )


def _inverse_centers(pipeline, feature_names: list[str]) -> np.ndarray:
    centers = pipeline.named_steps["kmeans"].cluster_centers_
    scaler = pipeline.named_steps["scaler"]
    return scaler.inverse_transform(centers)


def _boxplot_payload(X: np.ndarray, names: list[str], labels: np.ndarray) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for index, name in enumerate(names):
        payload[name] = {}
        for cluster in sorted(set(labels.tolist())):
            values = X[labels == cluster, index]
            payload[name][str(cluster)] = {
                "min": float(np.min(values)),
                "q1": float(np.quantile(values, 0.25)),
                "median": float(np.median(values)),
                "q3": float(np.quantile(values, 0.75)),
                "max": float(np.max(values)),
                "n": int(values.size),
            }
    return payload


def _tik_distribution(territories: np.ndarray, labels: np.ndarray) -> dict[str, dict[int, int]]:
    result: dict[str, dict[int, int]] = {}
    for territory, label in zip(territories.tolist(), labels.tolist(), strict=True):
        bucket = result.setdefault(str(territory), {})
        bucket[int(label)] = bucket.get(int(label), 0) + 1
    return result
