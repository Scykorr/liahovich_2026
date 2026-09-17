from __future__ import annotations

import numpy as np

from analytics_core.bootstrap import bootstrap_ari, stratified_subsample_indices
from analytics_core.clustering import fit_cluster_model, min_cluster_share


def test_min_cluster_share() -> None:
    labels = np.array([0, 0, 0, 1])
    assert min_cluster_share(labels) == 0.25


def test_kmeans_reproducible() -> None:
    rng = np.random.default_rng(0)
    X = rng.normal(size=(40, 3))
    a = fit_cluster_model(X, k=3, scaler="standard", seed=7, n_init=20)
    b = fit_cluster_model(X, k=3, scaler="standard", seed=7, n_init=20)
    assert np.array_equal(a["labels"], b["labels"])
    assert a["silhouette"] is not None


def test_stratified_and_bootstrap() -> None:
    rng = np.random.default_rng(1)
    X = np.vstack([rng.normal(0, 1, size=(20, 2)), rng.normal(3, 1, size=(20, 2))])
    territories = np.array(["a"] * 20 + ["b"] * 20)
    fitted = fit_cluster_model(X, k=2, scaler="standard", seed=1, n_init=20)
    indices = stratified_subsample_indices(territories, 0.8, np.random.default_rng(2))
    assert 1 <= indices.size <= 40
    ari = bootstrap_ari(
        X,
        territories,
        fitted["labels"],
        k=2,
        scaler="standard",
        seed=1,
        n_init=20,
        repeats=8,
        fraction=0.8,
    )
    assert -1.0 <= ari <= 1.0
