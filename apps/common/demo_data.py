from __future__ import annotations

import csv
import io
import random
from collections.abc import Iterable

HEADERS = [
    "ТИК",
    "УИК",
    "Избиратели",
    "Бюллетени в ящиках",
    "Вне участка",
    "Действительные",
    "Недействительные",
    "Иванов",
    "Петрова",
    "Сидоров",
]

CANONICAL_MAPPING = {
    "territory_code": "ТИК",
    "precinct_code": "УИК",
    "registered_voters": "Избиратели",
    "ballots_in_boxes": "Бюллетени в ящиках",
    "outside_ballots": "Вне участка",
    "valid_ballots": "Действительные",
    "invalid_ballots": "Недействительные",
}

CANDIDATE_COLUMNS = {
    "candidate_1": "Иванов",
    "candidate_2": "Петрова",
    "candidate_3": "Сидоров",
}

# Профили разведены по осям: явка, вне участка, недействительные и лидер не дублируют друг друга.
CLUSTERS = {
    "engaged": {"turnout": 0.84, "outside": 0.035, "invalid": 0.011, "shares": (0.37, 0.35, 0.28)},
    "home": {"turnout": 0.67, "outside": 0.23, "invalid": 0.014, "shares": (0.61, 0.25, 0.14)},
    "spoiled": {"turnout": 0.60, "outside": 0.05, "invalid": 0.088, "shares": (0.31, 0.52, 0.17)},
    "sidorov": {"turnout": 0.42, "outside": 0.07, "invalid": 0.017, "shares": (0.24, 0.21, 0.55)},
}

TERRITORIES: list[tuple[str, int, tuple[str, ...]]] = [
    ("2101", 14, ("engaged", "engaged", "home")),
    ("2102", 12, ("home", "home", "spoiled")),
    ("2103", 12, ("sidorov", "sidorov", "spoiled")),
    ("2104", 12, ("engaged", "spoiled", "sidorov")),
    ("2105", 12, ("home", "engaged", "spoiled")),
    ("2106", 12, ("spoiled", "sidorov", "home")),
    ("2107", 12, ("sidorov", "engaged", "home")),
    ("2108", 2, ("spoiled",)),
]


def _clamp(value: int, low: int, high: int) -> int:
    return max(low, min(high, value))


def _clip(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _split_votes(valid: int, shares: tuple[float, float, float]) -> tuple[int, int, int]:
    first = int(round(valid * shares[0]))
    second = int(round(valid * shares[1]))
    third = valid - first - second
    if third < 0:
        first = max(0, first + third)
        third = valid - first - second
    if third < 0:
        second = max(0, second + third)
        third = valid - first - second
    return max(0, first), max(0, second), max(0, third)


def _noisy_shares(rng: random.Random, base: tuple[float, float, float]) -> tuple[float, float, float]:
    raw = [max(0.05, share + rng.uniform(-0.10, 0.10)) for share in base]
    total = sum(raw) or 1.0
    return (raw[0] / total, raw[1] / total, raw[2] / total)


def _build_row(
    rng: random.Random,
    territory: str,
    precinct: str,
    kind: str,
    *,
    over_turnout: bool = False,
    outlier: bool = False,
) -> dict[str, str]:
    profile = CLUSTERS[kind]
    turnout = _clip(profile["turnout"] + rng.uniform(-0.07, 0.07), 0.28, 0.94)
    outside_share = _clip(profile["outside"] + rng.uniform(-0.025, 0.04), 0.008, 0.32)
    invalid_share = _clip(profile["invalid"] + rng.uniform(-0.008, 0.012), 0.004, 0.12)
    if outlier:
        turnout = _clip(0.93 + rng.uniform(0, 0.03), 0.9, 0.97)
        outside_share = _clip(0.26 + rng.uniform(-0.03, 0.04), 0.2, 0.34)
        invalid_share = 0.007
    voters = rng.randint(780, 1450)
    ballots = int(round(voters * turnout))
    if over_turnout:
        ballots = voters + rng.randint(18, 40)
    else:
        ballots = _clamp(ballots, 15, voters)
    invalid = _clamp(int(round(ballots * invalid_share)), 0, max(0, ballots - 4))
    valid = ballots - invalid
    outside = _clamp(int(round(ballots * outside_share)), 0, ballots)
    ivanov, petrova, sidorov = _split_votes(valid, _noisy_shares(rng, profile["shares"]))
    return {
        "ТИК": territory,
        "УИК": precinct,
        "Избиратели": str(voters),
        "Бюллетени в ящиках": str(ballots),
        "Вне участка": str(outside),
        "Действительные": str(valid),
        "Недействительные": str(invalid),
        "Иванов": str(ivanov),
        "Петрова": str(petrova),
        "Сидоров": str(sidorov),
    }


def iter_demo_rows(seed: int = 42) -> Iterable[dict[str, str]]:
    rng = random.Random(seed)
    for territory, count, kinds in TERRITORIES:
        for index in range(1, count + 1):
            kind = kinds[(index - 1) % len(kinds)]
            yield _build_row(
                rng,
                territory,
                f"{index:04d}",
                kind,
                over_turnout=territory == "2105" and index in {11, 12},
                outlier=territory == "2101" and index == 14,
            )


def rows_to_csv(rows: Iterable[dict[str, str]]) -> bytes:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=HEADERS, delimiter=";")
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    return ("\ufeff" + buffer.getvalue()).encode("utf-8")


def demo_valid_csv() -> bytes:
    return rows_to_csv(iter_demo_rows())


def demo_error_csv() -> bytes:
    rows = list(iter_demo_rows())[:18]
    broken = dict(rows[0])
    broken["Действительные"] = str(int(broken["Действительные"]) + 17)
    rows.append(broken)
    rows.append(dict(rows[1]))
    zero = dict(rows[2])
    zero["ТИК"] = "2199"
    zero["УИК"] = "0001"
    zero["Избиратели"] = "0"
    rows.append(zero)
    mismatch = dict(rows[3])
    mismatch["ТИК"] = "2198"
    mismatch["УИК"] = "0001"
    mismatch["Иванов"] = str(int(mismatch["Иванов"]) + 40)
    rows.append(mismatch)
    return rows_to_csv(rows)
