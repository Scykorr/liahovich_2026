from __future__ import annotations

from typing import Any

FEATURE_LABELS = {
    "turnout": "явка",
    "outside": "вне участка",
    "invalid": "недействительные",
}

SCALER_LABELS = {
    "standard": "стандартное",
    "robust": "устойчивое",
}

FIELD_LABELS = {
    "territory_code": "код территории",
    "precinct_code": "код УИК",
    "registered_voters": "избиратели",
    "ballots_in_boxes": "бюллетени в ящиках",
    "outside_ballots": "вне участка",
    "valid_ballots": "действительные",
    "invalid_ballots": "недействительные",
    "candidate_*": "голоса кандидатов",
    **FEATURE_LABELS,
}


def ru_clusters(count: int | str | None) -> str:
    try:
        number = int(count)
    except (TypeError, ValueError):
        return ""
    mod10 = number % 10
    mod100 = number % 100
    if mod10 == 1 and mod100 != 11:
        word = "кластер"
    elif mod10 in {2, 3, 4} and mod100 not in {12, 13, 14}:
        word = "кластера"
    else:
        word = "кластеров"
    return f"{number} {word}"


def human_label(value: str | None) -> str:
    if not value:
        return ""
    if value in FIELD_LABELS:
        return FIELD_LABELS[value]
    if value in SCALER_LABELS:
        return SCALER_LABELS[value]
    if value.startswith("candidate_"):
        return value.replace("candidate_", "кандидат ")
    return value


def join_feature_labels(values: list[str] | tuple[str, ...] | None) -> str:
    if not values:
        return ""
    return ", ".join(human_label(item) for item in values)


def format_centers(centers: Any) -> str:
    if not isinstance(centers, dict) or not centers:
        return ""
    parts = []
    for key, raw in centers.items():
        if isinstance(raw, float):
            parts.append(f"{human_label(str(key))}: {raw:.3f}")
        else:
            parts.append(f"{human_label(str(key))}: {raw}")
    return "; ".join(parts)
