from __future__ import annotations

import pytest
from django.urls import reverse

from apps.projects.models import ProjectMembership


@pytest.mark.django_db
def test_viewer_cannot_create_project(client, viewer) -> None:
    client.force_login(viewer)
    response = client.post(reverse("projects:create"), {"name": "X", "description": ""})
    assert response.status_code == 403


@pytest.mark.django_db
def test_stranger_gets_404(client, project, viewer) -> None:
    client.force_login(viewer)
    response = client.get(reverse("projects:detail", args=[project.uuid]))
    assert response.status_code == 404


@pytest.mark.django_db
def test_viewer_member_forbidden_upload(client, project, viewer) -> None:
    ProjectMembership.objects.create(project=project, user=viewer, role=ProjectMembership.Role.VIEWER)
    client.force_login(viewer)
    response = client.get(reverse("projects:dataset_upload", args=[project.uuid]))
    assert response.status_code == 403


@pytest.mark.django_db
def test_analyst_sees_own_project(client, project, analyst) -> None:
    client.force_login(analyst)
    response = client.get(reverse("projects:detail", args=[project.uuid]))
    assert response.status_code == 200
