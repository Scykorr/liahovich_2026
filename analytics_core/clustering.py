from __future__ import annotations

from typing import Any

import numpy as np
from sklearn.cluster import KMeans
from sklearn.metrics import (
    calinski_harabasz_score,
    davies_bouldin_score,
    silhouette_samples,
    silhouette_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import RobustScaler, StandardScaler

from analytics_core.types import ScalerName


def make_pipeline(scaler: ScalerName, k: int, seed: int, n_init: int) -> Pipeline:
    scaler_step = StandardScaler() if scaler == "standard" else RobustScaler()
    model = KMeans(n_clusters=k, init="k-means++", n_init=n_init, random_state=seed)
    return Pipeline([("scaler", scaler_step), ("kmeans", model)])


def fit_cluster_model(
    X: np.ndarray,
    k: int,
    scaler: ScalerName,
    seed: int,
    n_init: int,
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
    }
    n_labels = len(set(labels.tolist()))
    if n_labels >= 2 and X.shape[0] > n_labels:
        metrics["silhouette"] = float(silhouette_score(scaled, labels))
        metrics["calinski_harabasz"] = float(calinski_harabasz_score(scaled, labels))
        metrics["davies_bouldin"] = float(davies_bouldin_score(scaled, labels))
        metrics["silhouette_samples"] = silhouette_samples(scaled, labels).astype(float)
    return metrics


def min_cluster_share(labels: np.ndarray) -> float:
    if len(labels) == 0:
        return 0.0
    _, counts = np.unique(labels, return_counts=True)
    return float(counts.min() / len(labels))
