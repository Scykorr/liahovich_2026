from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from analytics_core.exceptions import DivisionByZeroError
from analytics_core.formulas import (
    candidate_share,
    invalid_share,
    leader_margin,
    opposition_sum,
    outside_share,
    turnout,
)


def test_turnout_basic() -> None:
    assert turnout(50, 100) == 50.0


def test_division_by_zero() -> None:
    with pytest.raises(DivisionByZeroError):
        turnout(10, 0)
    with pytest.raises(DivisionByZeroError):
        outside_share(1, 0)
    with pytest.raises(DivisionByZeroError):
        invalid_share(1, 0)
    with pytest.raises(DivisionByZeroError):
        candidate_share(1, 0)


def test_leader_margin_and_opposition() -> None:
    shares = {"a": 60.0, "b": 25.0, "c": 15.0}
    assert leader_margin(shares) == 35.0
    assert opposition_sum(shares, "a") == 40.0


@given(
    ballots=st.integers(min_value=0, max_value=10_000),
    registered=st.integers(min_value=1, max_value=10_000),
)
@settings(max_examples=80)
def test_turnout_non_negative(ballots: int, registered: int) -> None:
    value = turnout(ballots, registered)
    assert value >= 0
    assert value == 100.0 * ballots / registered


@given(
    outside=st.integers(min_value=0, max_value=5_000),
    invalid=st.integers(min_value=0, max_value=5_000),
    valid=st.integers(min_value=1, max_value=5_000),
)
@settings(max_examples=80)
def test_share_ranges_when_parts_within_total(outside: int, invalid: int, valid: int) -> None:
    ballots = valid + invalid
    assume_ballots = ballots > 0
    if not assume_ballots:
        return
    out = outside_share(min(outside, ballots), ballots)
    inv = invalid_share(invalid, ballots)
    share = candidate_share(valid, valid)
    assert 0 <= out <= 100
    assert 0 <= inv <= 100
    assert share == 100.0
