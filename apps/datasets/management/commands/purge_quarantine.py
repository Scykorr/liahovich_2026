from __future__ import annotations

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.datasets.models import Dataset


class Command(BaseCommand):
    help = "Удаляет карантинные файлы наборов старше N дней (по умолчанию BACKUP_RETENTION_DAYS)."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=None)

    def handle(self, *args, **options):
        from django.conf import settings

        days = options["days"] or settings.BACKUP_RETENTION_DAYS
        cutoff = timezone.now() - timedelta(days=days)
        qs = Dataset.objects.filter(status=Dataset.Status.QUARANTINED, created_at__lt=cutoff)
        count = qs.count()
        qs.delete()
        self.stdout.write(self.style.SUCCESS(f"Удалено карантинных наборов: {count}"))
