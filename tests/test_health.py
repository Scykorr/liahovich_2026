from __future__ import annotations

import pytest
from django.core.management import call_command
from django.test import Client
from django.test.utils import override_settings


@pytest.mark.django_db
def test_health_ok(client: Client) -> None:
    response = client.get("/health/")
    assert response.status_code == 200
    assert response.json()["database"] is True


@override_settings(
    DEBUG=False,
    SECRET_KEY="production-secret-key-for-check-deploy-32chars",
    ALLOWED_HOSTS=["example.test"],
    SECURE_SSL_REDIRECT=True,
    SESSION_COOKIE_SECURE=True,
    CSRF_COOKIE_SECURE=True,
    SECURE_HSTS_SECONDS=60,
    SECURE_HSTS_INCLUDE_SUBDOMAINS=True,
    CSRF_TRUSTED_ORIGINS=["https://example.test"],
)
def test_deploy_check() -> None:
    call_command("check", "--deploy")
