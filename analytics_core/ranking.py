from __future__ import annotations

from collections.abc import Sequence

import numpy as np

from analytics_core.types import CandidateResult


def percentile_ranks(values: Sequence[float]) -> list[float]:
    array = np.asarray(list(values), dtype=float)
    if array.size == 0:
        return []
    order = array.argsort()
    ranks = np.empty(array.size, dtype=float)
    ranks[order] = np.linspace(0.0, 1.0, array.size) if array.size > 1 else 1.0
    # ties: average rank of equal values
    _, inverse, counts = np.unique(array, return_inverse=True, return_counts=True)
    if np.any(counts > 1):
        sums = np.zeros(len(counts), dtype=float)
        np.add.at(sums, inverse, ranks)
        ranks = sums[inverse] / counts[inverse]
    return ranks.tolist()


def invert_davies_bouldin(values: Sequence[float | None]) -> list[float]:
    cleaned = [0.0 if value is None else float(value) for value in values]
    if not cleaned:
        return []
    ranks = percentile_ranks(cleaned)
    return [1.0 - rank for rank in ranks]


def internal_score(
    sil_rank: float,
    ch_rank: float,
    db_inverse_rank: float,
    sil_weight: float = 0.45,
    ch_weight: float = 0.30,
    db_weight: float = 0.25,
) -> float:
    return sil_weight * sil_rank + ch_weight * ch_rank + db_weight * db_inverse_rank


def total_score(
    internal: float,
    ari_percentile: float,
    internal_weight: float = 0.65,
    ari_weight: float = 0.35,
) -> float:
    return internal_weight * internal + ari_weight * ari_percentile


def apply_internal_ranks(
    candidates: list[CandidateResult],
    sil_weight: float = 0.45,
    ch_weight: float = 0.30,
    db_weight: float = 0.25,
) -> None:
    eligible = [item for item in candidates if not item.rejected]
    if not eligible:
        return
    sil_ranks = percentile_ranks([item.silhouette or 0.0 for item in eligible])
    ch_ranks = percentile_ranks([item.calinski_harabasz or 0.0 for item in eligible])
    db_inv = invert_davies_bouldin([item.davies_bouldin for item in eligible])
    for item, sil, ch, db in zip(eligible, sil_ranks, ch_ranks, db_inv, strict=True):
        item.internal_score = internal_score(sil, ch, db, sil_weight, ch_weight, db_weight)


def apply_total_scores(
    candidates: list[CandidateResult],
    internal_weight: float = 0.65,
    ari_weight: float = 0.35,
) -> None:
    eligible = [item for item in candidates if not item.rejected and item.internal_score is not None]
    if not eligible:
        return
    ari_values = [item.ari_mean if item.ari_mean is not None else 0.0 for item in eligible]
    ari_ranks = percentile_ranks(ari_values)
    for item, ari_rank in zip(eligible, ari_ranks, strict=True):
        item.ari_percentile = ari_rank
        item.total_score = total_score(item.internal_score or 0.0, ari_rank, internal_weight, ari_weight)


def recommend_index(candidates: list[CandidateResult], simplicity_delta: float = 0.02) -> int | None:
    scored = [
        (index, item)
        for index, item in enumerate(candidates)
        if not item.rejected and item.total_score is not None
    ]
    if not scored:
        return None
    scored.sort(key=lambda pair: pair[1].total_score or 0.0, reverse=True)
    best_index, best = scored[0]
    for index, item in scored[1:]:
        gap = (best.total_score or 0.0) - (item.total_score or 0.0)
        if gap < simplicity_delta and item.complexity < best.complexity:
            best_index, best = index, item
    return best_index
