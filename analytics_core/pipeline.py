from __future__ import annotations

from collections.abc import Callable
from itertools import combinations
from typing import Any

import numpy as np
import pandas as pd
import sklearn
from scipy import __version__ as scipy_version
from statsmodels import __version__ as statsmodels_version

from analytics_core.bootstrap import bootstrap_ari
from analytics_core.clustering import fit_cluster_model
from analytics_core.exceptions import DivisionByZeroError, PipelineError
from analytics_core.features import correlation_screen, drop_low_information, iterative_vif
from analytics_core.formulas import (
    candidate_share,
    invalid_share,
    leader_margin,
    opposition_sum,
    outside_share,
    turnout,
)
from analytics_core.ranking import apply_internal_ranks, apply_total_scores, recommend_index
from analytics_core.types import (
    CandidateResult,
    DroppedFeature,
    PipelineConfig,
    PipelineResult,
    PrecinctRow,
)

ProgressCallback = Callable[[int, str], None]


def library_versions() -> dict[str, str]:
    import numpy
    import pandas

    return {
        "numpy": numpy.__version__,
        "pandas": pandas.__version__,
        "scipy": scipy_version,
        "scikit-learn": sklearn.__version__,
        "statsmodels": statsmodels_version,
    }


def build_feature_frame(rows: list[PrecinctRow]) -> pd.DataFrame:
    records: list[dict[str, Any]] = []
    for row in rows:
        if row.registered_voters == 0 or row.ballots_in_boxes == 0 or row.valid_ballots == 0:
            raise DivisionByZeroError(
                f"Строка {row.row_number}: нулевой знаменатель, расчёт признаков невозможен"
            )
        shares = {
            name: candidate_share(votes, row.valid_ballots) for name, votes in row.candidate_votes.items()
        }
        leader_key = max(shares, key=shares.get) if shares else ""
        record: dict[str, Any] = {
            "precinct_id": f"{row.territory_code}:{row.precinct_code}",
            "territory_code": row.territory_code,
            "precinct_code": row.precinct_code,
            "row_number": row.row_number,
            "turnout": turnout(row.ballots_in_boxes, row.registered_voters),
            "outside": outside_share(row.outside_ballots, row.ballots_in_boxes),
            "invalid": invalid_share(row.invalid_ballots, row.ballots_in_boxes),
            "opposition_sum": opposition_sum(shares, leader_key) if shares else 0.0,
            "leader_margin": leader_margin(shares) if shares else 0.0,
        }
        record.update(shares)
        records.append(record)
    return pd.DataFrame.from_records(records)


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

    frame = build_feature_frame(rows)
    n_input = len(frame)
    excluded_ids: list[str] = []
    feature_pool = ["turnout", "outside", "invalid"]
    candidate_cols = [
        col
        for col in frame.columns
        if col not in {"precinct_id", "territory_code", "precinct_code", "row_number", "opposition_sum", "leader_margin"}
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
    _progress(18, "Корреляционный экран")
    working, dropped_corr = correlation_screen(
        working, config.corr_threshold, min_keep=config.feature_combo_min
    )
    _progress(24, "Итеративный VIF")
    working, dropped_vif, _vifs = iterative_vif(
        working, config.vif_threshold, min_keep=config.feature_combo_min
    )
    dropped: list[DroppedFeature] = dropped_low + dropped_corr + dropped_vif
    features = list(working.columns)
    if len(features) < config.feature_combo_min:
        raise PipelineError(
            f"После отбора осталось {len(features)} признаков, нужно минимум {config.feature_combo_min}"
        )

    outlier_ids = mark_outliers(frame, features, config.outlier_zscore)
    used = frame.copy()
    n_excluded = len(excluded_ids)
    n_used = len(used)
    if n_used < max(10, config.k_max + 1):
        raise PipelineError(f"Недостаточно строк для кластеризации: {n_used}")

    combo_min = config.feature_combo_min
    combo_max = min(config.feature_combo_max, len(features))
    combos = [
        list(combo)
        for size in range(combo_min, combo_max + 1)
        for combo in combinations(features, size)
    ]
    k_values = list(range(config.k_min, config.k_max + 1))
    total_models = max(1, len(combos) * len(k_values))
    candidates: list[CandidateResult] = []

    _progress(30, "Перебор моделей")
    X_full = used[features].to_numpy(dtype=float)
    territories = used["territory_code"].to_numpy()
    precinct_ids = used["precinct_id"].tolist()

    done = 0
    for combo in combos:
        cols_idx = [features.index(name) for name in combo]
        X = X_full[:, cols_idx]
        for k in k_values:
            done += 1
            percent = 30 + int(40 * done / total_models)
            _progress(percent, f"Модель {done}/{total_models}: k={k}, признаки={combo}")
            fitted = fit_cluster_model(
                X,
                k=k,
                scaler=config.scaler,
                seed=config.seed,
                n_init=config.n_init,
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
            sizes = {int(cluster): int(count) for cluster, count in zip(*np.unique(labels, return_counts=True))}
            centers = {}
            raw_centers = _inverse_centers(fitted["pipeline"], combo)
            for cluster_id, center in enumerate(raw_centers):
                centers[int(cluster_id)] = {
                    name: float(value) for name, value in zip(combo, center, strict=True)
                }
            boxplot = _boxplot_payload(X, combo, labels)
            tik_distribution = _tik_distribution(territories, labels)
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
                    n_used=n_used,
                    n_excluded=n_excluded,
                    labels=labels.tolist(),
                    distances=fitted["distances"].tolist(),
                    precinct_ids=list(precinct_ids),
                    centers=centers,
                    sizes=sizes,
                    boxplot=boxplot,
                    silhouette_samples=fitted["silhouette_samples"].tolist()
                    if len(fitted["silhouette_samples"])
                    else [],
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
    eligible.sort(key=lambda item: item.internal_score or 0.0, reverse=True)
    top = eligible[: config.bootstrap_top_n]
    _progress(75, "Bootstrap-устойчивость лучших кандидатов")
    for index, item in enumerate(top, start=1):
        _progress(75 + int(20 * index / max(len(top), 1)), f"Bootstrap {index}/{len(top)}")
        cols_idx = [features.index(name) for name in item.features]
        item.ari_mean = bootstrap_ari(
            X=X_full[:, cols_idx],
            territories=territories,
            reference_labels=np.asarray(item.labels),
            k=item.k,
            scaler=config.scaler,
            seed=config.seed,
            n_init=config.n_init,
            repeats=config.bootstrap_repeats,
            fraction=config.bootstrap_fraction,
        )
    apply_total_scores(
        candidates,
        internal_weight=config.internal_weight,
        ari_weight=config.ari_weight,
    )
    recommended = recommend_index(candidates, config.simplicity_delta)
    _progress(100, "Готово")
    warnings = []
    if outlier_ids:
        warnings.append(
            f"Помечено выбросов: {len(outlier_ids)}. Они не исключаются из расчёта при правиле mark_only."
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
