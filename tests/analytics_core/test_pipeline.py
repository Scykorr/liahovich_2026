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


def test_fixed_leader_is_constant_across_rows() -> None:
    from analytics_core.pipeline import fixed_leader_name

    rows = [
        PrecinctRow(2, "0100", "0001", 100, 100, 0, 100, 0, {"cand_a": 90, "cand_b": 10}),
        PrecinctRow(3, "0100", "0002", 100, 100, 0, 100, 0, {"cand_a": 10, "cand_b": 90}),
        PrecinctRow(4, "0200", "0003", 100, 80, 0, 80, 0, {"cand_a": 70, "cand_b": 10}),
    ]
    assert fixed_leader_name(rows) == "cand_a"
    frame = build_feature_frame(rows)
    assert frame.iloc[1]["leader_margin"] < 0
    assert abs(frame.iloc[1]["opposition_sum"] - frame.iloc[1]["cand_b"]) < 1e-6


def test_diagnostic_mode_rejects_exact_duplicate_only() -> None:
    rows = _rows()
    config = PipelineConfig(
        seed=3,
        k_min=2,
        k_max=2,
        feature_combo_min=2,
        feature_combo_max=2,
        subsample_repeats=0,
        feature_screen_mode="diagnostic",
        selected_features=["cand_a", "cand_b", "turnout"],
    )
    result = run_pipeline(rows, config)
    duplicated = [item for item in result.candidates if item.features == ["cand_a", "cand_b"]]
    assert duplicated
    assert all(item.rejected and "дубл" in item.reject_reason for item in duplicated)
    assert any(not item.rejected for item in result.candidates)
    assert result.models_calculated == len(result.candidates)
    assert result.models_admissible < result.models_calculated


def test_pipeline_reproducible_and_scores() -> None:
    config = PipelineConfig(
        seed=11,
        k_min=2,
        k_max=3,
        feature_combo_min=2,
        feature_combo_max=2,
        subsample_repeats=5,
        subsample_top_n=3,
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
