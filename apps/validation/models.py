from __future__ import annotations

from django.db import models

from apps.datasets.models import Dataset


class ValidationIssue(models.Model):
    class Level(models.TextChoices):
        ERROR = "error", "Ошибка"
        WARNING = "warning", "Предупреждение"

    dataset = models.ForeignKey(Dataset, related_name="issues", on_delete=models.CASCADE)
    level = models.CharField(max_length=16, choices=Level.choices)
    field = models.CharField(max_length=128, blank=True)
    row_number = models.PositiveIntegerField(null=True, blank=True)
    precinct_code = models.CharField(max_length=64, blank=True)
    territory_code = models.CharField(max_length=64, blank=True)
    code = models.CharField(max_length=64)
    message = models.TextField()
    details = models.JSONField(default=dict)

    class Meta:
        indexes = [
            models.Index(fields=["dataset", "level"]),
            models.Index(fields=["dataset", "field"]),
        ]
        verbose_name = "замечание качества"
        verbose_name_plural = "замечания качества"

    def __str__(self) -> str:
        return f"{self.level}:{self.code}"
