from __future__ import annotations

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models import QuerySet


class User(AbstractUser):
    class Role(models.TextChoices):
        ADMIN = "admin", "Администратор"
        ANALYST = "analyst", "Аналитик"
        VIEWER = "viewer", "Наблюдатель"

    role = models.CharField(max_length=20, choices=Role.choices, default=Role.VIEWER)

    class Meta:
        verbose_name = "пользователь"
        verbose_name_plural = "пользователи"

    def save(self, *args, **kwargs) -> None:
        if self.is_superuser:
            self.role = self.Role.ADMIN
        super().save(*args, **kwargs)

    @property
    def is_system_admin(self) -> bool:
        return self.role == self.Role.ADMIN or self.is_superuser

    def visible_projects(self) -> QuerySet:
        from apps.projects.models import Project

        if self.is_system_admin:
            return Project.objects.all()
        return Project.objects.filter(memberships__user=self).distinct()
