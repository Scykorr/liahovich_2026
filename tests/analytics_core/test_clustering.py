from __future__ import annotations

import numpy as np

from analytics_core.clustering import fit_cluster_model, min_cluster_share
from analytics_core.stability import repeated_subsample_stability, stratified_subsample_indices


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


def test_stratified_subsample_reports_spread() -> None:
    rng = np.random.default_rng(1)
    X = np.vstack([rng.normal(0, 1, size=(20, 2)), rng.normal(3, 1, size=(20, 2))])
    territories = np.array(["a"] * 20 + ["b"] * 20)
    fitted = fit_cluster_model(X, k=2, scaler="standard", seed=1, n_init=20)
    indices = stratified_subsample_indices(territories, 0.8, np.random.default_rng(2))
    assert indices.size == 32
    report = repeated_subsample_stability(
        X,
        territories,
        fitted["labels"],
        k=2,
        scaler="standard",
        seed=1,
        n_init=20,
        repeats=8,
        fraction=0.8,
        column_positions=[0, 1],
    )
    assert report.successes > 0
    assert report.ari_mean is not None and -1.0 <= report.ari_mean <= 1.0
    assert report.ari_p10 is not None and report.ari_p90 is not None
    assert report.ari_sd is not None
    assert len(report.indices) == 8


def test_silhouette_uses_reproducible_subsample() -> None:
    rng = np.random.default_rng(0)
    X = rng.normal(size=(40, 3))
    fitted = fit_cluster_model(X, k=3, scaler="standard", seed=7, n_init=20, silhouette_max_rows=12)
    assert fitted["silhouette"] is not None
    assert fitted["silhouette_rows"] == 12
    assert len(fitted["silhouette_samples"]) == 12
