from __future__ import annotations

from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management.base import BaseCommand, CommandError

from analytics_core.pipeline import synthetic_control_config
from apps.accounts.models import User
from apps.analytics.models import AnalysisRun
from apps.analytics.services import create_run, queue_run
from apps.datasets.services import import_records, save_mapping, upload_dataset
from apps.datasets.synthetic_kit import (
    DATA_NAME,
    GENERATOR_NAME,
    KIT_DIR,
    LABELS_NAME,
    NOTES_NAME,
    PASSPORT_NAME,
    PROJECT_NAME,
    SYNTHETIC_CANDIDATES,
    SYNTHETIC_MAPPING,
    kit_file,
    load_passport,
    verify_kit_hashes,
)
from apps.projects.models import Project
from apps.projects.services import create_project
from apps.validation.models import ValidationIssue


class Command(BaseCommand):
    help = "Импортирует синтетический контрольный набор 2026 и сверяет его с паспортом."

    def add_arguments(self, parser) -> None:
        parser.add_argument("--username", default="analyst")
        parser.add_argument(
            "--analyze",
            action="store_true",
            help="Запустить поиск моделей с параметрами паспорта эксперимента.",
        )
        parser.add_argument("--reset", action="store_true", help="Удалить ранее загруженный синтетический проект.")

    def handle(self, *args, **options) -> None:
        try:
            digests = verify_kit_hashes()
        except (FileNotFoundError, ValueError) as exc:
            raise CommandError(str(exc)) from exc
        passport = load_passport()
        user = User.objects.filter(username=options["username"]).first()
        if user is None:
            raise CommandError(f"Пользователь {options['username']} не найден. Сначала создайте аналитика.")
        if options["reset"]:
            Project.objects.filter(name=PROJECT_NAME).delete()
        project = Project.objects.filter(name=PROJECT_NAME).first()
        if project and project.datasets.exists() and not options["reset"]:
            raise CommandError("Синтетический проект уже загружен. Повторите команду с --reset.")
        if project is None:
            project = create_project(
                user=user,
                name=PROJECT_NAME,
                description=(
                    "Независимый синтетический набор. Файл эталонных групп не загружается как признак. "
                    f"Комплект: {KIT_DIR}."
                ),
            )
        uploaded = SimpleUploadedFile(DATA_NAME, kit_file(DATA_NAME).read_bytes(), content_type="text/csv")
        dataset = upload_dataset(user=user, project=project, uploaded_file=uploaded)
        save_mapping(
            user=user,
            dataset=dataset,
            mapping=SYNTHETIC_MAPPING,
            candidate_columns=SYNTHETIC_CANDIDATES,
            encoding="utf-8",
            delimiter=",",
        )
        import_records(user=user, dataset=dataset)
        dataset.refresh_from_db()
        errors = dataset.issues.filter(level=ValidationIssue.Level.ERROR).count()
        if errors:
            raise CommandError(f"В синтетическом наборе блокирующих ошибок: {errors}")
        if dataset.sha256 != digests[DATA_NAME]:
            raise CommandError("SHA-256 импортированного файла не совпал с паспортом")
        self.stdout.write(
            f"Импортировано строк: {dataset.row_count}. Паспорт: рассчитанных подмножеств "
            f"{passport['subset_count']}, допущенных моделей {passport['admissible_models']}."
        )
        self.stdout.write(f"Эталонные группы оставлены только в файле {LABELS_NAME}.")
        self.stdout.write(f"Рядом лежат {PASSPORT_NAME}, {NOTES_NAME}, {GENERATOR_NAME}.")
        if options["analyze"]:
            run = create_run(user=user, dataset=dataset, config=synthetic_control_config())
            queue_run(user=user, run=run)
            run.refresh_from_db()
            if run.status != AnalysisRun.Status.SUCCEEDED:
                raise CommandError(run.error_message or "Анализ синтетического набора не завершился")
            summary = run.summary_json
            self.stdout.write(
                "Анализ: "
                f"рассчитано {summary.get('models_calculated')}, "
                f"допущено {summary.get('models_admissible')}, "
                f"проверка устойчивости {summary.get('models_stability_checked')}, "
                f"прошли порог {summary.get('models_stability_passed')}."
            )
        self.stdout.write(self.style.SUCCESS(f"Проект «{project.name}» готов."))
