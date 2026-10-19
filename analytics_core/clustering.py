from __future__ import annotations

from typing import Any

from analytics_core.runtime import configure_threads

configure_threads()

import numpy as np  # noqa: E402
from sklearn.cluster import KMeans  # noqa: E402
from sklearn.metrics import (  # noqa: E402
    calinski_harabasz_score,
    davies_bouldin_score,
    silhouette_samples,
    silhouette_score,
)
from sklearn.pipeline import Pipeline  # noqa: E402
from sklearn.preprocessing import RobustScaler, StandardScaler  # noqa: E402

from analytics_core.types import ScalerName


def make_pipeline(scaler: ScalerName, k: int, seed: int, n_init: int) -> Pipeline:
    scaler_step = StandardScaler() if scaler == "standard" else RobustScaler()
    model = KMeans(
        n_clusters=k,
        init="k-means++",
        n_init=n_init,
        random_state=seed,
        algorithm="lloyd",
        max_iter=300,
        tol=1e-4,
    )
    return Pipeline([("scaler", scaler_step), ("kmeans", model)])


def fit_cluster_model(
    X: np.ndarray,
    k: int,
    scaler: ScalerName,
    seed: int,
    n_init: int,
    *,
    with_metrics: bool = True,
    silhouette_max_rows: int = 0,
) -> dict[str, Any]:
    pipeline = make_pipeline(scaler, k, seed, n_init)
    labels = pipeline.fit_predict(X)
    scaled = pipeline.named_steps["scaler"].transform(X)
    centers = pipeline.named_steps["kmeans"].cluster_centers_
    distances = np.linalg.norm(scaled - centers[labels], axis=1)
    share = min_cluster_share(labels)
    metrics: dict[str, Any] = {
        "pipeline": pipeline,
        "labels": labels.astype(int),
        "scaled": scaled,
        "centers": centers,
        "distances": distances.astype(float),
        "min_cluster_share": share,
        "silhouette": None,
        "calinski_harabasz": None,
        "davies_bouldin": None,
        "silhouette_samples": np.array([]),
        "silhouette_rows": 0,
    }
    if not with_metrics:
        return metrics
    n_labels = len(set(labels.tolist()))
    if n_labels >= 2 and X.shape[0] > n_labels:
        metrics["calinski_harabasz"] = float(calinski_harabasz_score(scaled, labels))
        metrics["davies_bouldin"] = float(davies_bouldin_score(scaled, labels))
        sample_idx = np.arange(X.shape[0])
        if silhouette_max_rows and X.shape[0] > silhouette_max_rows:
            rng = np.random.default_rng(seed)
            sample_idx = np.sort(rng.choice(X.shape[0], size=silhouette_max_rows, replace=False))
        labels_sample = labels[sample_idx]
        scaled_sample = scaled[sample_idx]
        n_labels_sample = len(set(labels_sample.tolist()))
        metrics["silhouette_rows"] = int(sample_idx.size)
        if n_labels_sample >= 2 and sample_idx.size > n_labels_sample:
            metrics["silhouette"] = float(silhouette_score(scaled_sample, labels_sample))
            metrics["silhouette_samples"] = silhouette_samples(scaled_sample, labels_sample).astype(float)
    return metrics


def min_cluster_share(labels: np.ndarray) -> float:
    if len(labels) == 0:
        return 0.0
    _, counts = np.unique(labels, return_counts=True)
    return float(counts.min() / len(labels))
