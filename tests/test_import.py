from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pytest
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from openpyxl import Workbook

from analytics_core.validation import has_blocking_errors, validate_records
from apps.datasets.io import read_tabular
from apps.datasets.services import import_records, records_to_core, save_mapping, upload_dataset
from tests.conftest import FIXTURES


@pytest.mark.django_db
def test_upload_csv_cyrillic_and_validate(analyst, project, valid_csv_file) -> None:
    dataset = upload_dataset(user=analyst, project=project, uploaded_file=valid_csv_file)
    assert dataset.sha256
    assert dataset.detected_columns
    mapping = {
        "territory_code": "ТИК",
        "precinct_code": "УИК",
        "registered_voters": "Избиратели",
        "ballots_in_boxes": "Бюллетени",
        "outside_ballots": "Вне участка",
        "valid_ballots": "Действительные",
        "invalid_ballots": "Недействительные",
    }
    save_mapping(
        user=analyst,
        dataset=dataset,
        mapping=mapping,
        candidate_columns={"candidate_1": "Кандидат А", "candidate_2": "Кандидат Б"},
        encoding="utf-8",
        delimiter=";",
    )
    import_records(user=analyst, dataset=dataset)
    dataset.refresh_from_db()
    assert dataset.row_count == 24
    issues = validate_records(records_to_core(dataset))
    assert not has_blocking_errors(issues)


@pytest.mark.django_db
def test_xlsx_import(analyst, project) -> None:
    workbook = Workbook()
    sheet = workbook.active
    csv_text = (FIXTURES / "valid_cyrillic.csv").read_text(encoding="utf-8")
    rows = [line.split(";") for line in csv_text.strip().splitlines()]
    for row in rows:
        sheet.append(row)
    buffer = BytesIO()
    workbook.save(buffer)
    uploaded = SimpleUploadedFile(
        "valid.xlsx",
        buffer.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    dataset = upload_dataset(user=analyst, project=project, uploaded_file=uploaded)
    assert dataset.original_filename.endswith(".xlsx")
    columns, data, *_ = read_tabular(Path(dataset.file.path))
    assert len(data) == 24


@pytest.mark.django_db
def test_balance_errors_block(analyst, project) -> None:
    raw = (FIXTURES / "balance_error.csv").read_bytes()
    uploaded = SimpleUploadedFile("bad.csv", raw, content_type="text/csv")
    dataset = upload_dataset(user=analyst, project=project, uploaded_file=uploaded)
    mapping = {
        "territory_code": "territory_code",
        "precinct_code": "precinct_code",
        "registered_voters": "registered_voters",
        "ballots_in_boxes": "ballots_in_boxes",
        "outside_ballots": "outside_ballots",
        "valid_ballots": "valid_ballots",
        "invalid_ballots": "invalid_ballots",
    }
    save_mapping(
        user=analyst,
        dataset=dataset,
        mapping=mapping,
        candidate_columns={"candidate_1": "candidate_a", "candidate_2": "candidate_b"},
    )
    import_records(user=analyst, dataset=dataset)
    assert dataset.issues.filter(level="error").exists()


@pytest.mark.django_db
def test_zero_and_duplicates(analyst, project) -> None:
    for name in ("zero_denominators.csv", "duplicates.csv"):
        uploaded = SimpleUploadedFile(name, (FIXTURES / name).read_bytes(), content_type="text/csv")
        dataset = upload_dataset(user=analyst, project=project, uploaded_file=uploaded)
        mapping = {
            "territory_code": "territory_code",
            "precinct_code": "precinct_code",
            "registered_voters": "registered_voters",
            "ballots_in_boxes": "ballots_in_boxes",
            "outside_ballots": "outside_ballots",
            "valid_ballots": "valid_ballots",
            "invalid_ballots": "invalid_ballots",
        }
        save_mapping(
            user=analyst,
            dataset=dataset,
            mapping=mapping,
            candidate_columns={"candidate_1": "candidate_a", "candidate_2": "candidate_b"},
        )
        import_records(user=analyst, dataset=dataset)
        assert dataset.issues.filter(level="error").exists()


@pytest.mark.django_db
def test_reject_bad_extension(analyst, project) -> None:
    uploaded = SimpleUploadedFile("note.exe", b"MZ", content_type="application/octet-stream")
    with pytest.raises(ValidationError):
        upload_dataset(user=analyst, project=project, uploaded_file=uploaded)
