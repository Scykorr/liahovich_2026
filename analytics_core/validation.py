from __future__ import annotations

from collections import defaultdict

from analytics_core.formulas import candidate_share, invalid_share, outside_share, turnout
from analytics_core.types import PrecinctRow, ValidationIssue

CANONICAL_FIELDS = (
    "territory_code",
    "precinct_code",
    "registered_voters",
    "ballots_in_boxes",
    "outside_ballots",
    "valid_ballots",
    "invalid_ballots",
)
COUNT_FIELDS = (
    "registered_voters",
    "ballots_in_boxes",
    "outside_ballots",
    "valid_ballots",
    "invalid_ballots",
)


def validate_records(rows: list[PrecinctRow], min_candidates: int = 2) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    seen: dict[tuple[str, str], int] = {}
    if not rows:
        issues.append(
            ValidationIssue(
                level="error",
                code="EMPTY",
                field="",
                message="Файл не содержит строк данных",
            )
        )
        return issues

    candidate_keys = _candidate_keys(rows)
    if len(candidate_keys) < min_candidates:
        issues.append(
            ValidationIssue(
                level="error",
                code="CANDIDATES_MIN",
                field="candidate_*",
                message=f"Нужно минимум {min_candidates} колонки кандидатов, найдено {len(candidate_keys)}",
                details={"count": len(candidate_keys)},
            )
        )

    for row in rows:
        loc = {
            "row_number": row.row_number,
            "territory_code": row.territory_code,
            "precinct_code": row.precinct_code,
        }
        if not str(row.territory_code).strip():
            issues.append(_error("REQUIRED", "territory_code", "Код территории обязателен", **loc))
        if not str(row.precinct_code).strip():
            issues.append(_error("REQUIRED", "precinct_code", "Код УИК обязателен", **loc))

        pair = (str(row.territory_code), str(row.precinct_code))
        if pair in seen:
            issues.append(
                _error(
                    "DUPLICATE",
                    "precinct_code",
                    f"Пара кодов {pair[0]}/{pair[1]} уже встречалась в строке {seen[pair]}",
                    **loc,
                    details={"first_row": seen[pair]},
                )
            )
        else:
            seen[pair] = row.row_number

        counts = {
            "registered_voters": row.registered_voters,
            "ballots_in_boxes": row.ballots_in_boxes,
            "outside_ballots": row.outside_ballots,
            "valid_ballots": row.valid_ballots,
            "invalid_ballots": row.invalid_ballots,
        }
        for field, value in counts.items():
            if not isinstance(value, int) or isinstance(value, bool):
                issues.append(
                    _error("TYPE", field, "Счётчик должен быть целым числом", **loc, details={"value": value})
                )
                continue
            if value < 0:
                issues.append(_error("NEGATIVE", field, "Счётчик не может быть отрицательным", **loc))

        if row.registered_voters == 0:
            issues.append(_error("ZERO_DENOMINATOR", "registered_voters", "Число избирателей равно нулю", **loc))
        if row.ballots_in_boxes == 0:
            issues.append(_error("ZERO_DENOMINATOR", "ballots_in_boxes", "Число бюллетеней в ящиках равно нулю", **loc))
        if row.valid_ballots == 0:
            issues.append(_error("ZERO_DENOMINATOR", "valid_ballots", "Число действительных бюллетеней равно нулю", **loc))

        if row.valid_ballots + row.invalid_ballots != row.ballots_in_boxes:
            issues.append(
                _error(
                    "BALANCE_BALLOTS",
                    "ballots_in_boxes",
                    "valid_ballots + invalid_ballots должно равняться ballots_in_boxes",
                    **loc,
                    details={
                        "valid_ballots": row.valid_ballots,
                        "invalid_ballots": row.invalid_ballots,
                        "ballots_in_boxes": row.ballots_in_boxes,
                    },
                )
            )

        candidate_sum = sum(row.candidate_votes.values()) if row.candidate_votes else 0
        if row.candidate_votes and candidate_sum != row.valid_ballots:
            issues.append(
                _error(
                    "BALANCE_CANDIDATES",
                    "candidate_*",
                    "Сумма голосов кандидатов должна равняться valid_ballots",
                    **loc,
                    details={"sum": candidate_sum, "valid_ballots": row.valid_ballots},
                )
            )

        if row.outside_ballots > row.ballots_in_boxes:
            issues.append(
                _error(
                    "PART_GT_TOTAL",
                    "outside_ballots",
                    "Вне участка не может превышать бюллетени в ящиках",
                    **loc,
                )
            )
        if row.invalid_ballots > row.ballots_in_boxes:
            issues.append(
                _error(
                    "PART_GT_TOTAL",
                    "invalid_ballots",
                    "Недействительные бюллетени не могут превышать бюллетени в ящиках",
                    **loc,
                )
            )
        if row.ballots_in_boxes > row.registered_voters:
            issues.append(
                ValidationIssue(
                    level="warning",
                    code="TURNOUT_OVER_100",
                    field="ballots_in_boxes",
                    message="Явка превышает 100 % — строка будет использована, но помечена",
                    **loc,
                )
            )
        for name, votes in row.candidate_votes.items():
            if not isinstance(votes, int) or isinstance(votes, bool) or votes < 0:
                issues.append(_error("NEGATIVE", name, "Голоса кандидата должны быть целым неотрицательным числом", **loc))
            elif votes > row.valid_ballots:
                issues.append(
                    _error(
                        "PART_GT_TOTAL",
                        name,
                        "Голоса кандидата не могут превышать valid_ballots",
                        **loc,
                    )
                )

        _try_formulas(row, issues, loc)

    _territory_warnings(rows, issues)
    return issues


def _try_formulas(row: PrecinctRow, issues: list[ValidationIssue], loc: dict) -> None:
    try:
        if row.registered_voters:
            turnout(row.ballots_in_boxes, row.registered_voters)
        if row.ballots_in_boxes:
            outside_share(row.outside_ballots, row.ballots_in_boxes)
            invalid_share(row.invalid_ballots, row.ballots_in_boxes)
        if row.valid_ballots:
            for votes in row.candidate_votes.values():
                candidate_share(votes, row.valid_ballots)
    except Exception as exc:  # noqa: BLE001
        issues.append(
            ValidationIssue(
                level="error",
                code="FORMULA",
                field="",
                message=str(exc),
                **loc,
            )
        )


def _territory_warnings(rows: list[PrecinctRow], issues: list[ValidationIssue]) -> None:
    by_tik: dict[str, int] = defaultdict(int)
    for row in rows:
        by_tik[row.territory_code] += 1
    for code, count in by_tik.items():
        if count < 3:
            issues.append(
                ValidationIssue(
                    level="warning",
                    code="SMALL_TERRITORY",
                    field="territory_code",
                    message=f"Территория {code} содержит только {count} УИК — стратификация bootstrap будет неустойчивой",
                    territory_code=code,
                    details={"count": count},
                )
            )


def _candidate_keys(rows: list[PrecinctRow]) -> set[str]:
    keys: set[str] = set()
    for row in rows:
        keys.update(row.candidate_votes.keys())
    return keys


def _error(code: str, field: str, message: str, **kwargs) -> ValidationIssue:
    return ValidationIssue(level="error", code=code, field=field, message=message, **kwargs)


def has_blocking_errors(issues: list[ValidationIssue]) -> bool:
    return any(issue.level == "error" for issue in issues)
