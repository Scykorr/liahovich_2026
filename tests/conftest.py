from __future__ import annotations

from pathlib import Path

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.accounts.models import User
from apps.projects.models import Project, ProjectMembership

FIXTURES = Path(__file__).resolve().parent / "fixtures"

@pytest.fixture(autouse=True)
def _media_root(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    settings.QUARANTINE_ROOT = tmp_path / "quarantine"


@pytest.fixture
def analyst(db) -> User:
    return User.objects.create_user(username="analyst", password="pass12345", role=User.Role.ANALYST)


@pytest.fixture
def viewer(db) -> User:
    return User.objects.create_user(username="viewer", password="pass12345", role=User.Role.VIEWER)


@pytest.fixture
def admin_user(db) -> User:
    return User.objects.create_superuser(username="admin", password="pass12345", email="admin@example.com")


@pytest.fixture
def project(analyst) -> Project:
    project = Project.objects.create(name="Тестовый проект", description="demo", created_by=analyst)
    ProjectMembership.objects.create(project=project, user=analyst, role=ProjectMembership.Role.ANALYST, created_by=analyst)
    return project


@pytest.fixture
def valid_csv_bytes() -> bytes:
    return (FIXTURES / "valid_cyrillic.csv").read_bytes()


@pytest.fixture
def valid_csv_file(valid_csv_bytes) -> SimpleUploadedFile:
    return SimpleUploadedFile("valid.csv", valid_csv_bytes, content_type="text/csv")
