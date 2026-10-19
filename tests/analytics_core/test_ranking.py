from __future__ import annotations

from analytics_core.ranking import recommend_index
from analytics_core.types import CandidateResult


def _candidate(**kwargs) -> CandidateResult:
    payload = dict(
        features=["turnout", "outside"],
        k=2,
        scaler="standard",
        silhouette=0.5,
        calinski_harabasz=20.0,
        davies_bouldin=0.8,
        min_cluster_share=0.2,
        total_score=0.5,
    )
    payload.update(kwargs)
    return CandidateResult(**payload)


def test_percentile_and_recommend(monkeypatch=None) -> None:
    from analytics_core.ranking import invert_davies_bouldin, percentile_ranks

    ranks = percentile_ranks([1.0, 2.0, 3.0])
    assert ranks[0] < ranks[1] < ranks[2]
    inverted = invert_davies_bouldin([0.2, 1.5, 3.0])
    assert inverted[0] > inverted[2]


def test_recommend_keeps_higher_internal_score_and_marks_alternative() -> None:
    items = [
        _candidate(
            k=6,
            features=["a", "b", "c", "d"],
            internal_score=0.90,
            ari_mean=0.80,
            ari_p10=0.70,
            total_score=0.80,
        ),
        _candidate(k=2, features=["a", "b"], internal_score=0.89, ari_mean=0.99, ari_p10=0.95, total_score=0.79),
    ]
    assert recommend_index(items, simplicity_delta=0.02) == 0
    assert items[1].is_alternative is True
    assert items[0].passes_stability is True


def test_unstable_model_is_not_recommended() -> None:
    items = [
        _candidate(internal_score=0.99, ari_mean=0.50, ari_p10=0.40, total_score=0.99),
        _candidate(k=3, features=["a", "b", "c"], internal_score=0.40, ari_mean=0.80, ari_p10=0.61, total_score=0.10),
    ]
    assert recommend_index(items) == 1


def test_missing_stability_is_not_zero_filled() -> None:
    from analytics_core.ranking import apply_total_scores

    items = [
        _candidate(internal_score=0.5, ari_mean=0.2, total_score=None, ari_percentile=None),
        _candidate(k=3, internal_score=0.9, ari_mean=None, total_score=None, ari_percentile=None),
    ]
    apply_total_scores(items)
    assert items[1].total_score is None
    assert items[1].ari_percentile is None
    assert items[0].total_score is not None


def test_internal_and_total_ranks() -> None:
    from analytics_core.ranking import apply_internal_ranks, apply_total_scores

    items = [
        _candidate(silhouette=0.9, calinski_harabasz=80, davies_bouldin=0.2),
        _candidate(silhouette=0.1, calinski_harabasz=10, davies_bouldin=2.0, k=3),
    ]
    apply_internal_ranks(items)
    items[0].ari_mean = 0.9
    items[1].ari_mean = 0.1
    apply_total_scores(items)
    assert items[0].internal_score > items[1].internal_score
    assert items[0].total_score > items[1].total_score

