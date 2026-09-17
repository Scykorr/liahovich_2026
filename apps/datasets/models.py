from __future__ import annotations

import hashlib
import uuid
from pathlib import Path

from django.core.exceptions import ValidationError
from django.db import models

from apps.common.models import TimestampedUUIDModel
from apps.projects.models import Project


def dataset_upload_to(instance: Dataset, filename: str) -> str:
    return f"datasets/{instance.project.uuid}/{instance.uuid}/{filename}"


class Dataset(TimestampedUUIDModel):
    class Status(models.TextChoices):
        QUARANTINED = "quarantined", "Карантин"
        MAPPED = "mapped", "Сопоставление"
        IMPORTED = "imported", "Импортирован"
        VALIDATED = "validated", "Проверен"
        FROZEN = "frozen", "Зафиксирован"

    project = models.ForeignKey(Project, related_name="datasets", on_delete=models.CASCADE)
    version = models.PositiveIntegerField("Версия")
    original_filename = models.CharField(max_length=255)
    stored_name = models.CharField(max_length=255)
    file = models.FileField(upload_to=dataset_upload_to)
    sha256 = models.CharField(max_length=64, db_index=True)
    schema_json = models.JSONField(default=dict)
    encoding = models.CharField(max_length=32, blank=True)
    delimiter = models.CharField(max_length=8, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.QUARANTINED)
    warnings_acknowledged = models.BooleanField(default=False)
    row_count = models.PositiveIntegerField(default=0)
    preview_rows = models.JSONField(default=list)
    detected_columns = models.JSONField(default=list)

    class Meta:
        unique_together = [("project", "version")]
        ordering = ["-version"]
        verbose_name = "набор данных"
        verbose_name_plural = "наборы данных"

    def __str__(self) -> str:
        return f"{self.project.name} v{self.version}"

    @property
    def is_frozen(self) -> bool:
        if self.status == self.Status.FROZEN:
            return True
        return self.runs.exclude(status="draft").exists()

    def freeze(self) -> None:
        if self.status != self.Status.FROZEN:
            self.status = self.Status.FROZEN
            self.save(update_fields=["status", "updated_at"])

    def clean(self) -> None:
        if self.pk and Dataset.objects.filter(pk=self.pk, status=self.Status.FROZEN).exists():
            current = Dataset.objects.get(pk=self.pk)
            tracked = (
                "file",
                "sha256",
                "schema_json",
                "encoding",
                "delimiter",
                "row_count",
            )
            for field in tracked:
                if getattr(self, field) != getattr(current, field):
                    raise ValidationError("Зафиксированный набор данных нельзя изменять")


class ColumnMapping(TimestampedUUIDModel):
    dataset = models.OneToOneField(Dataset, related_name="column_mapping", on_delete=models.CASCADE)
    mapping = models.JSONField(default=dict)
    candidate_columns = models.JSONField(default=dict)

    class Meta:
        verbose_name = "сопоставление колонок"
        verbose_name_plural = "сопоставления колонок"

    def __str__(self) -> str:
        return f"mapping {self.dataset_id}"


class PrecinctRecord(models.Model):
    dataset = models.ForeignKey(Dataset, related_name="records", on_delete=models.CASCADE)
    row_number = models.PositiveIntegerField()
    territory_code = models.CharField(max_length=64)
    precinct_code = models.CharField(max_length=64)
    registered_voters = models.BigIntegerField()
    ballots_in_boxes = models.BigIntegerField()
    outside_ballots = models.BigIntegerField()
    valid_ballots = models.BigIntegerField()
    invalid_ballots = models.BigIntegerField()
    candidate_votes = models.JSONField(default=dict)
    raw_data = models.JSONField(default=dict)
    is_excluded = models.BooleanField(default=False)
    is_outlier = models.BooleanField(default=False)

    class Meta:
        unique_together = [("dataset", "territory_code", "precinct_code")]
        indexes = [
            models.Index(fields=["dataset", "territory_code"]),
        ]
        verbose_name = "запись УИК"
        verbose_name_plural = "записи УИК"

    def __str__(self) -> str:
        return self.precinct_id

    @property
    def precinct_id(self) -> str:
        return f"{self.territory_code}:{self.precinct_code}"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_stored_name(original: str) -> str:
    suffix = Path(original).suffix.lower()
    return f"{uuid.uuid4().hex}{suffix}"
