from __future__ import annotations

from analytics_core.runtime import configure_threads

configure_threads()

from celery import Celery  # noqa: E402

os_env_loaded = False


def _load_env() -> None:
    global os_env_loaded
    if os_env_loaded:
        return
    try:
        from pathlib import Path

        from dotenv import load_dotenv

        load_dotenv(Path(__file__).resolve().parents[1] / ".env")
    except ImportError:
        pass
    os_env_loaded = True


_load_env()

import os  # noqa: E402

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

app = Celery("liahovich")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
