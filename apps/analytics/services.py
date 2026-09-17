from __future__ import annotations

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from analytics_core.exceptions import PipelineError
from analytics_core.pipeline import run_pipeline
from analytics_core.types import PipelineConfig
from apps.accounts.models import User
from apps.analytics.models import (
    AnalysisRun,
    ClusterAssignment,
    ClusterProfile,
    FeatureDefinition,
    ModelCandidate,
)
from apps.audit.services import log_event
from apps.datasets.models import Dataset, PrecinctRecord
from apps.datasets.services import records_to_core
from apps.validation.services import dataset_has_errors, dataset_has_warnings

FORMULA_LABELS = {
    "turnout": "100 * ballots_in_boxes / registered_voters",
    "outside": "100 * outside_ballots / ballots_in_boxes",
    "invalid": "100 * invalid_ballots / ballots_in_boxes",
}


class AnalysisNotReadyError(Exception):
    pass


def default_config(**overrides) -> PipelineConfig:
    config = PipelineConfig()
    for key, value in overrides.items():
        setattr(config, key, value)
    return config


@transaction.atomic
def create_run(*, user: User, dataset: Dataset, config: PipelineConfig, request=None) -> AnalysisRun:
    if dataset.status not in {Dataset.Status.VALIDATED, Dataset.Status.FROZEN, Dataset.Status.IMPORTED}:
        raise AnalysisNotReadyError("Сначала завершите импорт и проверку данных")
    if dataset_has_errors(dataset):
        raise AnalysisNotReadyError("Ошибки качества данных блокируют запуск")
    if dataset_has_warnings(dataset) and not dataset.warnings_acknowledged:
        raise AnalysisNotReadyError("Подтвердите предупреждения перед запуском")
    run = AnalysisRun.objects.create(
        project=dataset.project,
        dataset=dataset,
        status=AnalysisRun.Status.DRAFT,
        config_json=config.to_dict(),
        seed=config.seed,
        created_by=user,
    )
    log_event(user, "run_create", project=dataset.project, object_uuid=str(run.uuid), request=request)
    return run


@transaction.atomic
def queue_run(*, user: User, run: AnalysisRun, request=None) -> AnalysisRun:
    locked = AnalysisRun.objects.select_for_update().get(pk=run.pk)
    if locked.status in {AnalysisRun.Status.QUEUED, AnalysisRun.Status.RUNNING, AnalysisRun.Status.SUCCEEDED}:
        return locked
    if locked.status in {AnalysisRun.Status.FAILED, AnalysisRun.Status.CANCELLED}:
        locked.status = AnalysisRun.Status.DRAFT
    dataset = Dataset.objects.select_for_update().get(pk=locked.dataset_id)
    if dataset_has_errors(dataset):
        raise AnalysisNotReadyError("Ошибки качества данных блокируют запуск")
    locked.status = AnalysisRun.Status.QUEUED
    locked.progress = 1
    locked.progress_message = "Постановка в очередь"
    locked.error_message = ""
    locked.save(update_fields=["status", "progress", "progress_message", "error_message", "updated_at"])
    dataset.freeze()
    log_event(user, "run_queue", project=locked.project, object_uuid=str(locked.uuid), request=request)
    run_uuid = str(locked.uuid)
    if settings.CELERY_TASK_ALWAYS_EAGER:
        execute_run(run_uuid)
    else:
        from apps.analytics.tasks import run_analysis_task

        transaction.on_commit(lambda: _store_task_id(run_uuid, run_analysis_task.delay(run_uuid).id))
    return locked


def _store_task_id(run_uuid: str, task_id: str | None) -> None:
    AnalysisRun.objects.filter(uuid=run_uuid).update(celery_task_id=task_id or "")


@transaction.atomic
def cancel_run(*, user: User, run: AnalysisRun, request=None) -> AnalysisRun:
    locked = AnalysisRun.objects.select_for_update().get(pk=run.pk)
    if locked.status in {AnalysisRun.Status.SUCCEEDED, AnalysisRun.Status.FAILED}:
        return locked
    locked.status = AnalysisRun.Status.CANCELLED
    locked.progress_message = "Отменён"
    locked.save(update_fields=["status", "progress_message", "updated_at"])
    log_event(user, "run_cancel", project=locked.project, object_uuid=str(locked.uuid), request=request)
    return locked


def execute_run(run_uuid: str) -> AnalysisRun:
    run = AnalysisRun.objects.select_related("dataset").get(uuid=run_uuid)
    if run.status == AnalysisRun.Status.SUCCEEDED:
        return run
    if run.status == AnalysisRun.Status.CANCELLED:
        return run
    run.status = AnalysisRun.Status.RUNNING
    run.progress = 5
    run.progress_message = "Старт"
    run.save(update_fields=["status", "progress", "progress_message", "updated_at"])

    def progress(percent: int, message: str) -> None:
        AnalysisRun.objects.filter(pk=run.pk).exclude(status=AnalysisRun.Status.CANCELLED).update(
            progress=percent,
            progress_message=message[:255],
        )

    def cancelled() -> bool:
        return AnalysisRun.objects.filter(pk=run.pk, status=AnalysisRun.Status.CANCELLED).exists()

    try:
        rows = records_to_core(run.dataset)
        config = PipelineConfig.from_dict(run.config_json)
        result = run_pipeline(rows, config, progress=progress, cancelled=cancelled)
    except PipelineError as exc:
        run.refresh_from_db()
        if run.status == AnalysisRun.Status.CANCELLED:
            return run
        run.status = AnalysisRun.Status.FAILED
        run.error_message = str(exc)
        run.progress_message = "Ошибка"
        run.save(update_fields=["status", "error_message", "progress_message", "updated_at"])
        return run
    except Exception as exc:  # noqa: BLE001
        run.status = AnalysisRun.Status.FAILED
        run.error_message = f"Внутренняя ошибка расчёта: {exc}"
        run.progress_message = "Ошибка"
        run.save(update_fields=["status", "error_message", "progress_message", "updated_at"])
        return run

    _persist_result(run, result)
    return AnalysisRun.objects.get(pk=run.pk)


def _persist_result(run: AnalysisRun, result) -> None:
    FeatureDefinition.objects.filter(run=run).delete()
    ModelCandidate.objects.filter(run=run).delete()
    included = set(result.feature_columns)
    FeatureDefinition.objects.bulk_create(
        [
            FeatureDefinition(
                run=run,
                name=name,
                formula=FORMULA_LABELS.get(name, "100 * candidate_votes / valid_ballots"),
                included=True,
            )
            for name in result.feature_columns
        ]
    )
    FeatureDefinition.objects.bulk_create(
        [
            FeatureDefinition(
                run=run,
                name=item.name,
                included=False,
                drop_reason=item.reason,
                details=item.details,
            )
            for item in result.dropped_features
            if item.name not in included
        ]
    )
    records = {
        f"{item.territory_code}:{item.precinct_code}": item
        for item in PrecinctRecord.objects.filter(dataset=run.dataset)
    }
    saved_candidates: list[ModelCandidate] = []
    for candidate in result.candidates:
        model = ModelCandidate.objects.create(
            run=run,
            features=candidate.features,
            k=candidate.k,
            scaler=candidate.scaler,
            silhouette=candidate.silhouette,
            calinski_harabasz=candidate.calinski_harabasz,
            davies_bouldin=candidate.davies_bouldin,
            min_cluster_share=candidate.min_cluster_share,
            internal_score=candidate.internal_score,
            ari_mean=candidate.ari_mean,
            ari_percentile=candidate.ari_percentile,
            total_score=candidate.total_score,
            rejected=candidate.rejected,
            reject_reason=candidate.reject_reason,
            n_used=candidate.n_used,
            n_excluded=candidate.n_excluded,
            complexity=candidate.complexity,
            boxplot=candidate.boxplot,
            silhouette_samples=candidate.silhouette_samples,
            tik_distribution=candidate.tik_distribution,
            labels=candidate.labels,
            precinct_ids=candidate.precinct_ids,
        )
        saved_candidates.append(model)
        if candidate.rejected:
            continue
        assignments = []
        for precinct_id, label, distance in zip(
            candidate.precinct_ids, candidate.labels, candidate.distances, strict=True
        ):
            record = records.get(precinct_id)
            if record is None:
                continue
            assignments.append(
                ClusterAssignment(
                    candidate=model,
                    record=record,
                    cluster_id=int(label),
                    distance_to_center=float(distance),
                )
            )
        ClusterAssignment.objects.bulk_create(assignments, batch_size=1000)
        profiles = []
        total = max(sum(candidate.sizes.values()), 1)
        for cluster_id, size in candidate.sizes.items():
            profiles.append(
                ClusterProfile(
                    candidate=model,
                    cluster_id=int(cluster_id),
                    size=int(size),
                    share=float(size) / total,
                    centers=candidate.centers.get(int(cluster_id), {}),
                    stats=candidate.boxplot,
                )
            )
        ClusterProfile.objects.bulk_create(profiles)
    if result.outlier_ids:
        ids = result.outlier_ids
        territory_precincts = [item.split(":", 1) for item in ids if ":" in item]
        for territory, precinct in territory_precincts:
            PrecinctRecord.objects.filter(
                dataset=run.dataset, territory_code=territory, precinct_code=precinct
            ).update(is_outlier=True)

    recommended = None
    if result.recommended_index is not None and 0 <= result.recommended_index < len(saved_candidates):
        recommended = saved_candidates[result.recommended_index]
    run.recommended_candidate = recommended
    run.selected_candidate = recommended
    run.library_versions = result.library_versions
    run.n_used = result.n_used
    run.n_excluded = result.n_excluded
    run.warnings_json = result.warnings
    run.outlier_ids = result.outlier_ids
    run.status = AnalysisRun.Status.SUCCEEDED
    run.progress = 100
    run.progress_message = "Готово"
    run.save()


@transaction.atomic
def select_candidate(*, user: User, run: AnalysisRun, candidate: ModelCandidate, request=None) -> AnalysisRun:
    if candidate.run_id != run.id:
        raise AnalysisNotReadyError("Кандидат не принадлежит запуску")
    run.selected_candidate = candidate
    run.save(update_fields=["selected_candidate", "updated_at"])
    log_event(user, "run_select_model", project=run.project, object_uuid=str(run.uuid), request=request)
    return run


@transaction.atomic
def publish_run(*, user: User, run: AnalysisRun, request=None) -> AnalysisRun:
    if run.status != AnalysisRun.Status.SUCCEEDED or run.selected_candidate_id is None:
        raise AnalysisNotReadyError("Опубликовать можно только успешный запуск с выбранной моделью")
    run.published_at = timezone.now()
    run.published_by = user
    run.save(update_fields=["published_at", "published_by", "updated_at"])
    log_event(user, "run_publish", project=run.project, object_uuid=str(run.uuid), request=request)
    return run
