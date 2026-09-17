from __future__ import annotations

from analytics_core.types import PrecinctRow
from analytics_core.validation import has_blocking_errors, validate_records


def _row(**kwargs) -> PrecinctRow:
    base = dict(
        row_number=2,
        territory_code="0100",
        precinct_code="0001",
        registered_voters=1000,
        ballots_in_boxes=700,
        outside_ballots=40,
        valid_ballots=680,
        invalid_ballots=20,
        candidate_votes={"a": 400, "b": 280},
    )
    base.update(kwargs)
    return PrecinctRow(**base)


def test_valid_row_has_no_errors() -> None:
    issues = validate_records([_row()])
    assert not has_blocking_errors(issues)


def test_balance_and_duplicate_and_zero() -> None:
    rows = [
        _row(valid_ballots=600, invalid_ballots=20),
        _row(row_number=3, precinct_code="0001", registered_voters=0),
        _row(row_number=4, precinct_code="0002", candidate_votes={"a": 100, "b": 20}),
    ]
    issues = validate_records(rows)
    codes = {issue.code for issue in issues if issue.level == "error"}
    assert "BALANCE_BALLOTS" in codes
    assert "DUPLICATE" in codes
    assert "ZERO_DENOMINATOR" in codes
    assert "BALANCE_CANDIDATES" in codes


def test_codes_kept_as_strings() -> None:
    issues = validate_records([_row(territory_code="0100", precinct_code="0001")])
    assert not has_blocking_errors(issues)
