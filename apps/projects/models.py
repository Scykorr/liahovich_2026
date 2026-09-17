from __future__ import annotations

from django.conf import settings
from django.db import models

from apps.common.models import TimestampedUUIDModel


class Project(TimestampedUUIDModel):
    name = models.CharField("Название", max_length=255)
    description = models.TextField("Описание", blank=True)
    is_archived = models.BooleanField("В архиве", default=False)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "проект"
        verbose_name_plural = "проекты"

    def __str__(self) -> str:
        return self.name

    def next_dataset_version(self) -> int:
        last = self.datasets.order_by("-version").first()
        return 1 if last is None else last.version + 1


class ProjectMembership(models.Model):
    class Role(models.TextChoices):
        ANALYST = "analyst", "Аналитик"
        VIEWER = "viewer", "Наблюдатель"

    project = models.ForeignKey(Project, related_name="memberships", on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="project_memberships", on_delete=models.CASCADE)
    role = models.CharField("Роль", max_length=20, choices=Role.choices)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="memberships_granted",
    )

    class Meta:
        unique_together = [("project", "user")]
        verbose_name = "участник проекта"
        verbose_name_plural = "участники проекта"

    def __str__(self) -> str:
        return f"{self.user} @ {self.project} ({self.role})"
