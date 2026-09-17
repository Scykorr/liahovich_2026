from __future__ import annotations

from analytics_core.pipeline import build_feature_frame, run_pipeline
from analytics_core.types import PipelineConfig, PrecinctRow


def _rows() -> list[PrecinctRow]:
    rows = []
    row_number = 2
    for tik in ("0100", "0200"):
        for i in range(1, 13):
            registered = 800 + i * 20 + (10 if tik == "0200" else 0)
            valid = 400 + i * 15
            invalid = 10 + (i % 3)
            ballots = valid + invalid
            a = 200 + i * 10
            b = valid - a
            rows.append(
                PrecinctRow(
                    row_number=row_number,
                    territory_code=tik,
                    precinct_code=f"{i:04d}",
                    registered_voters=registered,
                    ballots_in_boxes=ballots,
                    outside_ballots=min(30 + i, ballots),
                    valid_ballots=valid,
                    invalid_ballots=invalid,
                    candidate_votes={"cand_a": a, "cand_b": b},
                )
            )
            row_number += 1
    return rows


def test_feature_frame_formulas() -> None:
    frame = build_feature_frame(_rows()[:1])
    row = frame.iloc[0]
    assert row["turnout"] > 0
    assert abs(row["cand_a"] + row["cand_b"] - 100) < 1e-6


def test_pipeline_reproducible_and_scores() -> None:
    config = PipelineConfig(
        seed=11,
        k_min=2,
        k_max=3,
        feature_combo_min=2,
        feature_combo_max=2,
        bootstrap_repeats=5,
        bootstrap_top_n=3,
        n_init=20,
    )
    first = run_pipeline(_rows(), config)
    second = run_pipeline(_rows(), config)
    assert first.recommended_index == second.recommended_index
    assert first.candidates
    assert any(not item.rejected for item in first.candidates)
    for left, right in zip(first.candidates, second.candidates, strict=True):
        assert left.labels == right.labels
        assert left.total_score == right.total_score
