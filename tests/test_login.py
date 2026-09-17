from __future__ import annotations

import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_login_and_dashboard(client, analyst) -> None:
    response = client.post(reverse("accounts:login"), {"username": "analyst", "password": "pass12345"})
    assert response.status_code == 302
    dashboard = client.get(reverse("projects:dashboard"))
    assert dashboard.status_code == 200
    assert "Проекты" in dashboard.content.decode("utf-8")
