from __future__ import annotations

from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management.base import BaseCommand, CommandError

from analytics_core.types import PipelineConfig
from apps.accounts.models import User
from apps.analytics.models import AnalysisRun
from apps.analytics.services import cancel_run, create_run, publish_run, queue_run
from apps.common.demo_data import (
    CANONICAL_MAPPING,
    CANDIDATE_COLUMNS,
    demo_error_csv,
    demo_valid_csv,
)
from apps.datasets.services import acknowledge_warnings, import_records, save_mapping, upload_dataset
from apps.projects.models import Project, ProjectMembership
from apps.projects.services import add_member, create_project
from apps.validation.models import ValidationIssue

DEMO_PROJECTS = (
    "Кластеры УИК — демо 2024",
    "Импорт в работе",
    "Новый район",
)


class Command(BaseCommand):
    help = "Создаёт демонстрационные проекты, данные УИК и завершённый анализ."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Удалить ранее созданные демо-проекты и заполнить заново.",
        )

    def handle(self, *args, **options) -> None:
        existing = Project.objects.filter(name__in=DEMO_PROJECTS)
        if existing.exists() and not options["reset"]:
            raise CommandError("Демо-данные уже есть. Запустите: python manage.py seed_demo --reset")
        if options["reset"]:
            deleted, _ = existing.delete()
            self.stdout.write(f"Удалены прежние демо-проекты ({deleted} объектов).")

        admin = self._ensure_user("admin", "admin12345", superuser=True)
        analyst = self._ensure_user("analyst", "pass12345", role=User.Role.ANALYST)
        viewer = self._ensure_user("viewer", "pass12345", role=User.Role.VIEWER)

        main = self._seed_main_project(admin, analyst, viewer)
        self._seed_mapping_project(analyst)
        create_project(
            user=analyst,
            name="Новый район",
            description="Пустой проект, чтобы было видно состояние без загрузок.",
        )

        self.stdout.write(self.style.SUCCESS("Демо-данные готовы."))
        self.stdout.write(f"Главный проект: {main.name} ({main.uuid})")
        self.stdout.write("Вход: admin / admin12345, analyst / pass12345, viewer / pass12345")

    def _ensure_user(self, username: str, password: str, *, role: str | None = None, superuser: bool = False) -> User:
        user = User.objects.filter(username=username).first()
        if user:
            if role and not user.is_superuser:
                user.role = role
                user.save(update_fields=["role"])
            return user
        if superuser:
            return User.objects.create_superuser(username=username, email=f"{username}@localhost", password=password)
        return User.objects.create_user(
            username=username,
            email=f"{username}@localhost",
            password=password,
            role=role or User.Role.VIEWER,
        )

    def _upload(self, user: User, project: Project, filename: str, content: bytes):
        uploaded = SimpleUploadedFile(filename, content, content_type="text/csv")
        dataset = upload_dataset(user=user, project=project, uploaded_file=uploaded)
        save_mapping(
            user=user,
            dataset=dataset,
            mapping=CANONICAL_MAPPING,
            candidate_columns=CANDIDATE_COLUMNS,
            encoding="utf-8-sig",
            delimiter=";",
        )
        return dataset

    def _seed_main_project(self, admin: User, analyst: User, viewer: User) -> Project:
        project = create_project(
            user=analyst,
            name="Кластеры УИК — демо 2024",
            description=(
                "Демонстрационный набор: несколько ТИК, три кандидата, предупреждения качества, "
                "завершённый запуск и опубликованный отчёт."
            ),
        )
        add_member(actor=admin, project=project, user=viewer, role=ProjectMembership.Role.VIEWER)

        dataset = self._upload(analyst, project, "протоколы_уик_демо.csv", demo_valid_csv())
        import_records(user=analyst, dataset=dataset)
        warnings = dataset.issues.filter(level=ValidationIssue.Level.WARNING).count()
        errors = dataset.issues.filter(level=ValidationIssue.Level.ERROR).count()
        if errors:
            raise CommandError(f"В демо-CSV есть блокирующие ошибки: {errors}")
        if warnings:
            acknowledge_warnings(user=analyst, dataset=dataset)
        self.stdout.write(f"Набор v{dataset.version}: {dataset.row_count} УИК, предупреждений {warnings}.")

        config = PipelineConfig(
            seed=42,
            k_min=2,
            k_max=4,
            feature_combo_min=2,
            feature_combo_max=3,
            bootstrap_repeats=12,
            bootstrap_top_n=5,
            n_init=20,
        )
        self.stdout.write("Считается кластеризация, это может занять минуту...")
        run = create_run(user=analyst, dataset=dataset, config=config)
        queue_run(user=analyst, run=run)
        run.refresh_from_db()
        if run.status != AnalysisRun.Status.SUCCEEDED:
            raise CommandError(run.error_message or "Анализ не завершился успешно")
        publish_run(user=analyst, run=run)
        self.stdout.write(
            f"Запуск {run.uuid}: кандидатов {run.candidates.count()}, "
            f"использовано {run.n_used}, исключено {run.n_excluded}."
        )

        draft = create_run(user=analyst, dataset=dataset, config=config)
        self.stdout.write(f"Черновик запуска: {draft.uuid}")
        cancelled = create_run(user=analyst, dataset=dataset, config=config)
        cancel_run(user=analyst, run=cancelled)

        broken = self._upload(analyst, project, "протоколы_с_ошибками.csv", demo_error_csv())
        import_records(user=analyst, dataset=broken)
        self.stdout.write(
            f"Набор v{broken.version}: ошибок {broken.issues.filter(level='error').count()} "
            f"(запуск по нему заблокирован)."
        )
        return project

    def _seed_mapping_project(self, analyst: User) -> Project:
        project = create_project(
            user=analyst,
            name="Импорт в работе",
            description="Файл загружен и сопоставлен, импорт ещё не подтверждён — можно пройти мастер дальше.",
        )
        dataset = self._upload(analyst, project, "черновик_протокола.csv", demo_valid_csv())
        self.stdout.write(f"Черновик импорта: {project.name}, статус {dataset.get_status_display()}.")
        return project
