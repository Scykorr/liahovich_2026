from __future__ import annotations

from analytics_core.exceptions import DivisionByZeroError


def _require_nonzero(denominator: float | int, name: str) -> None:
    if denominator == 0:
        raise DivisionByZeroError(f"Деление на ноль: знаменатель «{name}» равен 0")


def turnout(ballots_in_boxes: float | int, registered_voters: float | int) -> float:
    _require_nonzero(registered_voters, "registered_voters")
    return 100.0 * float(ballots_in_boxes) / float(registered_voters)


def outside_share(outside_ballots: float | int, ballots_in_boxes: float | int) -> float:
    _require_nonzero(ballots_in_boxes, "ballots_in_boxes")
    return 100.0 * float(outside_ballots) / float(ballots_in_boxes)


def invalid_share(invalid_ballots: float | int, ballots_in_boxes: float | int) -> float:
    _require_nonzero(ballots_in_boxes, "ballots_in_boxes")
    return 100.0 * float(invalid_ballots) / float(ballots_in_boxes)


def candidate_share(candidate_votes: float | int, valid_ballots: float | int) -> float:
    _require_nonzero(valid_ballots, "valid_ballots")
    return 100.0 * float(candidate_votes) / float(valid_ballots)


def opposition_sum(candidate_shares: dict[str, float], leader_key: str) -> float:
    return sum(value for key, value in candidate_shares.items() if key != leader_key)


def leader_margin(candidate_shares: dict[str, float]) -> float:
    if not candidate_shares:
        raise DivisionByZeroError("Нет долей кандидатов для расчёта отрыва лидера")
    ordered = sorted(candidate_shares.values(), reverse=True)
    if len(ordered) == 1:
        return ordered[0]
    return ordered[0] - ordered[1]
