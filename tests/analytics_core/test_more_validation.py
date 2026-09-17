from __future__ import annotations

import pytest

from analytics_core.exceptions import DivisionByZeroError
from analytics_core.formulas import leader_margin
from analytics_core.types import PrecinctRow
from analytics_core.validation import validate_records


def test_empty_dataset_error() -> None:
    issues = validate_records([])
    assert any(issue.code == "EMPTY" for issue in issues)


def test_leader_margin_errors() -> None:
    with pytest.raises(DivisionByZeroError):
        leader_margin({})
    assert leader_margin({"a": 12.0}) == 12.0


def test_required_codes() -> None:
    row = PrecinctRow(
        row_number=2,
        territory_code=" ",
        precinct_code="",
        registered_voters=10,
        ballots_in_boxes=4,
        outside_ballots=1,
        valid_ballots=3,
        invalid_ballots=1,
        candidate_votes={"a": 2, "b": 1},
    )
    codes = {issue.code for issue in validate_records([row])}
    assert "REQUIRED" in codes
