from __future__ import annotations

import csv
from io import StringIO

from analytics_core.types import ValidationIssue as CoreIssue
from apps.datasets.models import Dataset
from apps.validation.models import ValidationIssue


def persist_issues(dataset: Dataset, issues: list[CoreIssue]) -> None:
    ValidationIssue.objects.filter(dataset=dataset).delete()
    ValidationIssue.objects.bulk_create(
        [
            ValidationIssue(
                dataset=dataset,
                level=issue.level,
                field=issue.field,
                row_number=issue.row_number,
                precinct_code=issue.precinct_code,
                territory_code=issue.territory_code,
                code=issue.code,
                message=issue.message,
                details=issue.details,
            )
            for issue in issues
        ],
        batch_size=500,
    )


def issues_csv(dataset: Dataset) -> str:
    buffer = StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["level", "code", "field", "row_number", "territory_code", "precinct_code", "message"])
    for issue in dataset.issues.order_by("level", "row_number", "id"):
        writer.writerow(
            [
                issue.level,
                issue.code,
                issue.field,
                issue.row_number or "",
                issue.territory_code,
                issue.precinct_code,
                issue.message,
            ]
        )
    return buffer.getvalue()


def dataset_has_errors(dataset: Dataset) -> bool:
    return dataset.issues.filter(level=ValidationIssue.Level.ERROR).exists()


def dataset_has_warnings(dataset: Dataset) -> bool:
    return dataset.issues.filter(level=ValidationIssue.Level.WARNING).exists()
