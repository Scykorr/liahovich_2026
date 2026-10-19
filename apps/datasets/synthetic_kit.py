from __future__ import annotations

import hashlib
import json
from pathlib import Path

KIT_DIR = Path(__file__).resolve().parents[2] / "data" / "synthetic"
DATA_NAME = "Ляхович_синтетические_данные_2026.csv"
LABELS_NAME = "Ляхович_эталонные_группы_ТОЛЬКО_для_проверки.csv"
PASSPORT_NAME = "Ляхович_паспорт_эксперимента_2026.json"
NOTES_NAME = "Ляхович_инструкция_к_синтетическим_данным.txt"
GENERATOR_NAME = "generate_and_validate_synthetic.py"

SYNTHETIC_MAPPING = {
    "territory_code": "territory_code",
    "precinct_code": "precinct_code",
    "registered_voters": "registered_voters",
    "ballots_in_boxes": "ballots_in_boxes",
    "outside_ballots": "outside_ballots",
    "valid_ballots": "valid_ballots",
    "invalid_ballots": "invalid_ballots",
}

SYNTHETIC_CANDIDATES = {
    "candidate_A": "candidate_A",
    "candidate_B": "candidate_B",
    "candidate_C": "candidate_C",
    "candidate_D": "candidate_D",
}

PROJECT_NAME = "Синтетический контрольный набор 2026"


def kit_file(name: str) -> Path:
    path = KIT_DIR / name
    if not path.is_file():
        raise FileNotFoundError(f"В комплекте нет файла {name}")
    return path


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_passport() -> dict:
    return json.loads(kit_file(PASSPORT_NAME).read_text(encoding="utf-8"))


def verify_kit_hashes() -> dict[str, str]:
    passport = load_passport()
    expected = passport["files"]
    actual = {
        DATA_NAME: sha256_file(kit_file(DATA_NAME)),
        LABELS_NAME: sha256_file(kit_file(LABELS_NAME)),
    }
    for name, digest in actual.items():
        if expected.get(name) != digest:
            raise ValueError(f"SHA-256 файла {name} не совпадает с паспортом эксперимента")
    return actual
