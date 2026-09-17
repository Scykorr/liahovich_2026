from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.metrics import adjusted_rand_score

from analytics_core.clustering import fit_cluster_model
from analytics_core.types import ScalerName


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
        n = max(1, int(round(group.size * fraction)))
        n = min(n, group.size)
        chosen = rng.choice(group, size=n, replace=False)
        selected.extend(int(i) for i in chosen)
    return np.asarray(sorted(selected), dtype=int)


def bootstrap_ari(
    X: np.ndarray,
    territories: np.ndarray,
    reference_labels: np.ndarray,
    k: int,
    scaler: ScalerName,
    seed: int,
    n_init: int,
    repeats: int,
    fraction: float,
) -> float:
    rng = np.random.default_rng(seed)
    scores: list[float] = []
    for repeat in range(repeats):
        local_rng = np.random.default_rng(int(rng.integers(0, 2**31 - 1)))
        indices = stratified_subsample_indices(territories, fraction, local_rng)
        if len(set(reference_labels[indices].tolist())) < 2 or indices.size <= k:
            continue
        fitted = fit_cluster_model(X[indices], k=k, scaler=scaler, seed=seed + repeat, n_init=n_init)
        subsample_labels = fitted["labels"]
        scores.append(float(adjusted_rand_score(reference_labels[indices], subsample_labels)))
    if not scores:
        return 0.0
    return float(np.mean(scores))


def ids_frame(precinct_ids: list[str]) -> pd.Series:
    return pd.Series(precinct_ids, name="precinct_id")
