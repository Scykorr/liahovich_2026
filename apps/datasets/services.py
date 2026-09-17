from __future__ import annotations

from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.db import transaction
from django.utils.text import get_valid_filename

from analytics_core.types import PrecinctRow
from analytics_core.validation import validate_records
from apps.accounts.models import User
from apps.audit.services import log_event
from apps.datasets.io import (
    CANONICAL_FIELDS,
    guess_candidates,
    guess_mapping,
    read_tabular,
    sanitize_filename,
    validate_upload,
)
from apps.datasets.models import (
    ColumnMapping,
    Dataset,
    PrecinctRecord,
    safe_stored_name,
    sha256_file,
)
from apps.projects.models import Project
from apps.validation.models import ValidationIssue
from apps.validation.services import persist_issues


def _rate_limit_ok(user: User) -> bool:
    from django.core.cache import cache

    key = f"upload-rate:{user.pk}"
    count = cache.get(key, 0)
    limit = getattr(settings, "UPLOAD_RATE_LIMIT_PER_HOUR", 20)
    if count >= limit:
        return False
    cache.set(key, count + 1, 60 * 60)
    return True


@transaction.atomic
def upload_dataset(*, user: User, project: Project, uploaded_file, request=None) -> Dataset:
    if not _rate_limit_ok(user):
        raise ValidationError("Слишком много загрузок. Попробуйте позже.")
    filename = sanitize_filename(uploaded_file.name)
    validate_upload(uploaded_file, filename)
    stored = safe_stored_name(get_valid_filename(filename))
    version = project.next_dataset_version()
    dataset = Dataset(
        project=project,
        version=version,
        original_filename=filename,
        stored_name=stored,
        created_by=user,
        status=Dataset.Status.QUARANTINED,
    )
    quarantine_dir = Path(settings.QUARANTINE_ROOT)
    quarantine_dir.mkdir(parents=True, exist_ok=True)
    quarantine_path = quarantine_dir / stored
    uploaded_file.seek(0)
    quarantine_path.write_bytes(uploaded_file.read())
    dataset.sha256 = sha256_file(quarantine_path)
    dataset.file.save(stored, ContentFile(quarantine_path.read_bytes()), save=False)
    columns, rows, encoding, delimiter = read_tabular(quarantine_path)
    dataset.encoding = encoding
    dataset.delimiter = delimiter
    dataset.detected_columns = columns
    dataset.preview_rows = rows[:20]
    dataset.schema_json = {
        "columns": columns,
        "row_count_raw": len(rows),
        "source": filename,
    }
    dataset.save()
    mapping = guess_mapping(columns)
    candidates = {col: col for col in guess_candidates(columns, mapping)}
    ColumnMapping.objects.create(
        dataset=dataset,
        mapping=mapping,
        candidate_columns=candidates,
        created_by=user,
    )
    log_event(
        user,
        "dataset_upload",
        project=project,
        object_uuid=str(dataset.uuid),
        request=request,
        extra={"filename": filename, "sha256": dataset.sha256, "version": version},
    )
    return dataset


@transaction.atomic
def save_mapping(
    *,
    user: User,
    dataset: Dataset,
    mapping: dict[str, str],
    candidate_columns: dict[str, str],
    encoding: str = "",
    delimiter: str = "",
    request=None,
) -> Dataset:
    if dataset.is_frozen:
        raise ValidationError("Набор данных зафиксирован. Создайте новую версию.")
    missing = [field for field in CANONICAL_FIELDS if not mapping.get(field)]
    if missing:
        raise ValidationError(f"Не сопоставлены обязательные поля: {', '.join(missing)}")
    if len(candidate_columns) < 2:
        raise ValidationError("Нужно выбрать минимум двух кандидатов")
    if encoding:
        dataset.encoding = encoding
    if delimiter:
        dataset.delimiter = delimiter
    column_mapping, _ = ColumnMapping.objects.get_or_create(dataset=dataset, defaults={"created_by": user})
    column_mapping.mapping = mapping
    column_mapping.candidate_columns = candidate_columns
    column_mapping.created_by = user
    column_mapping.save()
    path = Path(dataset.file.path)
    columns, rows, encoding, delimiter = read_tabular(
        path,
        encoding=dataset.encoding or None,
        delimiter=dataset.delimiter or None,
    )
    dataset.encoding = encoding
    dataset.delimiter = delimiter
    dataset.detected_columns = columns
    dataset.preview_rows = rows[:20]
    dataset.status = Dataset.Status.MAPPED
    dataset.save()
    log_event(user, "dataset_mapping", project=dataset.project, object_uuid=str(dataset.uuid), request=request)
    return dataset


def _to_int(value: str, field: str, row_number: int) -> int:
    text = str(value).strip().replace(" ", "").replace("\xa0", "")
    if text == "":
        raise ValidationError(f"Строка {row_number}: пустое значение {field}")
    try:
        number = int(float(text.replace(",", "."))) if re_looks_numeric(text) else int(text)
    except ValueError as exc:
        raise ValidationError(f"Строка {row_number}: поле {field} должно быть целым числом") from exc
    return number


def re_looks_numeric(text: str) -> bool:
    return "," in text or "." in text


@transaction.atomic
def import_records(*, user: User, dataset: Dataset, request=None) -> Dataset:
    if dataset.is_frozen:
        raise ValidationError("Набор данных зафиксирован. Создайте новую версию.")
    mapping = dataset.column_mapping.mapping
    candidates = dataset.column_mapping.candidate_columns
    path = Path(dataset.file.path)
    _columns, rows, encoding, delimiter = read_tabular(
        path,
        encoding=dataset.encoding or None,
        delimiter=dataset.delimiter or None,
    )
    dataset.encoding = encoding
    dataset.delimiter = delimiter
    PrecinctRecord.objects.filter(dataset=dataset).delete()
    ValidationIssue.objects.filter(dataset=dataset).delete()
    records: list[PrecinctRecord] = []
    core_rows: list[PrecinctRow] = []
    for index, row in enumerate(rows, start=2):
        candidate_votes = {}
        for key, column in candidates.items():
            candidate_votes[key] = _to_int(row.get(column, "0"), key, index)
        precinct = PrecinctRecord(
            dataset=dataset,
            row_number=index,
            territory_code=str(row.get(mapping["territory_code"], "")).strip(),
            precinct_code=str(row.get(mapping["precinct_code"], "")).strip(),
            registered_voters=_to_int(row.get(mapping["registered_voters"], ""), "registered_voters", index),
            ballots_in_boxes=_to_int(row.get(mapping["ballots_in_boxes"], ""), "ballots_in_boxes", index),
            outside_ballots=_to_int(row.get(mapping["outside_ballots"], ""), "outside_ballots", index),
            valid_ballots=_to_int(row.get(mapping["valid_ballots"], ""), "valid_ballots", index),
            invalid_ballots=_to_int(row.get(mapping["invalid_ballots"], ""), "invalid_ballots", index),
            candidate_votes=candidate_votes,
            raw_data=row,
        )
        records.append(precinct)
        core_rows.append(
            PrecinctRow(
                row_number=index,
                territory_code=precinct.territory_code,
                precinct_code=precinct.precinct_code,
                registered_voters=precinct.registered_voters,
                ballots_in_boxes=precinct.ballots_in_boxes,
                outside_ballots=precinct.outside_ballots,
                valid_ballots=precinct.valid_ballots,
                invalid_ballots=precinct.invalid_ballots,
                candidate_votes=candidate_votes,
            )
        )
    issues = validate_records(core_rows)
    persist_issues(dataset, issues)
    unique: list[PrecinctRecord] = []
    seen: set[tuple[str, str]] = set()
    for record in records:
        key = (record.territory_code, record.precinct_code)
        if key in seen:
            continue
        seen.add(key)
        unique.append(record)
    PrecinctRecord.objects.bulk_create(unique, batch_size=500)
    dataset.row_count = len(unique)
    dataset.schema_json = {
        "columns": dataset.detected_columns,
        "mapping": mapping,
        "candidates": candidates,
        "row_count": len(records),
        "encoding": dataset.encoding,
        "delimiter": dataset.delimiter,
        "sha256": dataset.sha256,
    }
    dataset.status = Dataset.Status.VALIDATED
    dataset.warnings_acknowledged = False
    dataset.save()
    log_event(user, "dataset_import", project=dataset.project, object_uuid=str(dataset.uuid), request=request)
    return dataset


def acknowledge_warnings(*, user: User, dataset: Dataset, request=None) -> Dataset:
    if dataset.is_frozen:
        raise ValidationError("Набор данных зафиксирован")
    dataset.warnings_acknowledged = True
    dataset.save(update_fields=["warnings_acknowledged", "updated_at"])
    log_event(user, "dataset_ack_warnings", project=dataset.project, object_uuid=str(dataset.uuid), request=request)
    return dataset


def records_to_core(dataset: Dataset) -> list[PrecinctRow]:
    rows = []
    for record in dataset.records.order_by("row_number"):
        rows.append(
            PrecinctRow(
                row_number=record.row_number,
                territory_code=record.territory_code,
                precinct_code=record.precinct_code,
                registered_voters=record.registered_voters,
                ballots_in_boxes=record.ballots_in_boxes,
                outside_ballots=record.outside_ballots,
                valid_ballots=record.valid_ballots,
                invalid_ballots=record.invalid_ballots,
                candidate_votes=record.candidate_votes,
            )
        )
    return rows
