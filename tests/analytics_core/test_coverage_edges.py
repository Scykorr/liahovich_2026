from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from analytics_core.clustering import min_cluster_share
from analytics_core.exceptions import PipelineError
from analytics_core.features import drop_low_information
from analytics_core.pipeline import run_pipeline
from analytics_core.ranking import (
    apply_internal_ranks,
    apply_total_scores,
    invert_davies_bouldin,
    percentile_ranks,
    recommend_index,
)
from analytics_core.types import PipelineConfig, PrecinctRow
from analytics_core.validation import validate_records
from tests.analytics_core.test_pipeline import _rows


def test_empty_helpers() -> None:
    assert min_cluster_share(np.array([])) == 0.0
    assert percentile_ranks([]) == []
    assert invert_davies_bouldin([]) == []
    apply_internal_ranks([])
    apply_total_scores([])
    assert recommend_index([]) is None


def test_drop_constant_feature() -> None:
    frame = pd.DataFrame({"a": [1.0, 1.0, 1.0, 1.0], "b": [1.0, 2.0, 3.0, 8.0], "c": [2.0, 5.0, 1.0, 9.0]})
    kept, dropped = drop_low_information(frame, min_unique=3)
    assert any(item.name == "a" for item in dropped)
    assert "b" in kept.columns


def test_pipeline_guards() -> None:
    with pytest.raises(PipelineError):
        run_pipeline([], PipelineConfig())
    with pytest.raises(PipelineError):
        run_pipeline(
            _rows(),
            PipelineConfig(k_min=2, k_max=2, feature_combo_min=2, feature_combo_max=2, bootstrap_repeats=2),
            cancelled=lambda: True,
        )
    with pytest.raises(PipelineError):
        run_pipeline(_rows()[:1], PipelineConfig(selected_features=["missing_feature"]))


def test_single_candidate_error() -> None:
    row = PrecinctRow(
        row_number=2,
        territory_code="1",
        precinct_code="1",
        registered_voters=10,
        ballots_in_boxes=5,
        outside_ballots=6,
        valid_ballots=4,
        invalid_ballots=2,
        candidate_votes={"only": 4},
    )
    codes = {issue.code for issue in validate_records([row])}
    assert "CANDIDATES_MIN" in codes
    assert "PART_GT_TOTAL" in codes
