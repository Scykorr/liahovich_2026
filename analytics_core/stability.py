"""Стратифицированная подвыборка без возвращения. Это не bootstrap."""

from __future__ import annotations

from analytics_core.runtime import configure_threads

configure_threads()

import numpy as np  # noqa: E402
from sklearn.metrics import adjusted_rand_score  # noqa: E402

from analytics_core.clustering import fit_cluster_model
from analytics_core.types import ScalerName, StabilityReport


def stratified_subsample_indices(
    territories: np.ndarray,
    fraction: float,
    rng: np.random.Generator,
) -> np.ndarray:
    selected: list[int] = []
    for territory in np.unique(territories):
        group = np.flatnonzero(territories == territory)
        if group.size == 0:
            continue
        n = int(np.floor(group.size * fraction))
        n = max(1, min(n, group.size))
        chosen = rng.choice(group, size=n, replace=False)
        selected.extend(int(i) for i in chosen)
    return np.asarray(sorted(selected), dtype=int)


def repeated_subsample_stability(
    X: np.ndarray,
    territories: np.ndarray,
    reference_labels: np.ndarray,
    k: int,
    scaler: ScalerName,
    seed: int,
    n_init: int,
    repeats: int,
    fraction: float,
    column_positions: list[int] | None = None,
) -> StabilityReport:
    offset = int(sum(column_positions or []))
    rng = np.random.default_rng(int(seed) + 100 + int(k) + offset)
    scores: list[float] = []
    indices_out: list[list[int]] = []
    for repeat in range(repeats):
        indices = stratified_subsample_indices(territories, fraction, rng)
        indices_out.append([int(i) for i in indices.tolist()])
        if indices.size <= k or len(set(reference_labels[indices].tolist())) < 2:
            continue
        fitted = fit_cluster_model(
            X[indices],
            k=k,
            scaler=scaler,
            seed=seed + repeat,
            n_init=n_init,
            with_metrics=False,
        )
        scores.append(float(adjusted_rand_score(reference_labels[indices], fitted["labels"])))
    if not scores:
        return StabilityReport(
            ari_mean=None,
            ari_p10=None,
            ari_p90=None,
            ari_sd=None,
            successes=0,
            repeats=repeats,
            indices=indices_out,
        )
    array = np.asarray(scores, dtype=float)
    return StabilityReport(
        ari_mean=float(np.mean(array)),
        ari_p10=float(np.percentile(array, 10)),
        ari_p90=float(np.percentile(array, 90)),
        ari_sd=float(np.std(array)),
        successes=int(array.size),
        repeats=repeats,
        indices=indices_out,
    )
