from __future__ import annotations

from apps.analytics.services import execute_run
from celery import shared_task


@shared_task(bind=True, ignore_result=False, acks_late=True, max_retries=0)
def run_analysis_task(self, run_uuid: str) -> str:
    run = execute_run(run_uuid)
    return str(run.status)
