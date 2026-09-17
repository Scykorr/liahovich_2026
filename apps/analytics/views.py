from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import Http404, HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_http_methods

from apps.analytics.forms import AnalysisConfigForm
from apps.analytics.health import healthcheck as healthcheck_impl
from apps.analytics.models import AnalysisRun, ModelCandidate
from apps.analytics.services import (
    AnalysisNotReadyError,
    cancel_run,
    create_run,
    publish_run,
    queue_run,
    select_candidate,
)
from apps.common.access import can_view_run, get_visible_project, require_project_role
from apps.datasets.io import CANONICAL_FIELDS, CANONICAL_LABELS
from apps.datasets.models import Dataset
from apps.datasets.services import (
    acknowledge_warnings,
    import_records,
    save_mapping,
    upload_dataset,
)
from apps.projects.models import ProjectMembership
from apps.reports.services import (
    export_assignments_csv,
    export_assignments_xlsx,
    export_passport_json,
    export_report_html,
    export_report_pdf,
)
from apps.validation.services import issues_csv


def healthcheck(request: HttpRequest) -> JsonResponse:
    return healthcheck_impl(request)


@login_required
@require_http_methods(["GET", "POST"])
def dataset_upload(request: HttpRequest, project_uuid) -> HttpResponse:
    project = get_visible_project(request.user, project_uuid)
    require_project_role(request.user, project, ProjectMembership.Role.ANALYST)
    error = ""
    if request.method == "POST":
        uploaded = request.FILES.get("file")
        if not uploaded:
            error = "Выберите файл"
        else:
            try:
                dataset = upload_dataset(user=request.user, project=project, uploaded_file=uploaded, request=request)
                return redirect("projects:dataset_mapping", project_uuid=project.uuid, dataset_uuid=dataset.uuid)
            except ValidationError as exc:
                error = "; ".join(exc.messages)
    return render(request, "datasets/upload.html", {"project": project, "error": error})


@login_required
@require_http_methods(["GET", "POST"])
def dataset_mapping(request: HttpRequest, project_uuid, dataset_uuid) -> HttpResponse:
    project = get_visible_project(request.user, project_uuid)
    require_project_role(request.user, project, ProjectMembership.Role.ANALYST)
    dataset = get_object_or_404(Dataset, uuid=dataset_uuid, project=project)
    mapping_obj = dataset.column_mapping
    error = ""
    if request.method == "POST":
        mapping = {field: request.POST.get(f"map_{field}", "") for field in CANONICAL_FIELDS}
        selected = request.POST.getlist("candidates")
        candidate_columns = {f"candidate_{index}": name for index, name in enumerate(selected, start=1)}
        try:
            save_mapping(
                user=request.user,
                dataset=dataset,
                mapping=mapping,
                candidate_columns=candidate_columns,
                encoding=request.POST.get("encoding", ""),
                delimiter=request.POST.get("delimiter", ""),
                request=request,
            )
            import_records(user=request.user, dataset=dataset, request=request)
            return redirect("projects:dataset_quality", project_uuid=project.uuid, dataset_uuid=dataset.uuid)
        except ValidationError as exc:
            error = "; ".join(exc.messages)
    return render(
        request,
        "datasets/mapping.html",
        {
            "project": project,
            "dataset": dataset,
            "columns": dataset.detected_columns,
            "mapping": mapping_obj.mapping,
            "candidates": mapping_obj.candidate_columns,
            "canonical": CANONICAL_FIELDS,
            "labels": CANONICAL_LABELS,
            "preview": dataset.preview_rows,
            "candidate_names": list(mapping_obj.candidate_columns.values()),
            "error": error,
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def dataset_quality(request: HttpRequest, project_uuid, dataset_uuid) -> HttpResponse:
    project = get_visible_project(request.user, project_uuid)
    require_project_role(request.user, project, ProjectMembership.Role.ANALYST)
    dataset = get_object_or_404(Dataset, uuid=dataset_uuid, project=project)
    if request.method == "POST" and request.POST.get("ack"):
        acknowledge_warnings(user=request.user, dataset=dataset, request=request)
        return redirect("projects:dataset_quality", project_uuid=project.uuid, dataset_uuid=dataset.uuid)
    level = request.GET.get("level", "")
    field = request.GET.get("field", "")
    issues = dataset.issues.all()
    if level:
        issues = issues.filter(level=level)
    if field:
        issues = issues.filter(field=field)
    fields = dataset.issues.values_list("field", flat=True).distinct()
    return render(
        request,
        "datasets/quality.html",
        {
            "project": project,
            "dataset": dataset,
            "issues": issues.order_by("level", "row_number"),
            "fields": fields,
            "level": level,
            "field": field,
            "error_count": dataset.issues.filter(level="error").count(),
            "warning_count": dataset.issues.filter(level="warning").count(),
        },
    )


@login_required
@require_GET
def dataset_issues_csv(request: HttpRequest, project_uuid, dataset_uuid) -> HttpResponse:
    project = get_visible_project(request.user, project_uuid)
    require_project_role(request.user, project, ProjectMembership.Role.ANALYST)
    dataset = get_object_or_404(Dataset, uuid=dataset_uuid, project=project)
    content = issues_csv(dataset)
    response = HttpResponse(content, content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="quality_{dataset.uuid}.csv"'
    return response


@login_required
@require_http_methods(["GET", "POST"])
def run_create(request: HttpRequest, project_uuid) -> HttpResponse:
    project = get_visible_project(request.user, project_uuid)
    require_project_role(request.user, project, ProjectMembership.Role.ANALYST)
    datasets = project.datasets.filter(status__in=["validated", "frozen"])
    form = AnalysisConfigForm(request.POST or None)
    error = ""
    if request.method == "POST" and form.is_valid():
        dataset = get_object_or_404(Dataset, uuid=request.POST.get("dataset"), project=project)
        try:
            run = create_run(user=request.user, dataset=dataset, config=form.to_config(), request=request)
            queue_run(user=request.user, run=run, request=request)
            return redirect("projects:run_progress", project_uuid=project.uuid, run_uuid=run.uuid)
        except AnalysisNotReadyError as exc:
            error = str(exc)
    return render(
        request,
        "analytics/run_form.html",
        {"project": project, "form": form, "datasets": datasets, "error": error},
    )


@login_required
@require_http_methods(["GET", "POST"])
def run_progress(request: HttpRequest, project_uuid, run_uuid) -> HttpResponse:
    project = get_visible_project(request.user, project_uuid)
    run = get_object_or_404(AnalysisRun, uuid=run_uuid, project=project)
    if not can_view_run(request.user, project, run):
        raise Http404("Запуск не найден")
    if request.method == "POST" and request.POST.get("cancel"):
        require_project_role(request.user, project, ProjectMembership.Role.ANALYST)
        cancel_run(user=request.user, run=run, request=request)
        return redirect("projects:run_progress", project_uuid=project.uuid, run_uuid=run.uuid)
    template = "analytics/progress_partial.html" if request.headers.get("HX-Request") else "analytics/progress.html"
    return render(request, template, {"project": project, "run": run})


@login_required
@require_GET
def run_candidates(request: HttpRequest, project_uuid, run_uuid) -> HttpResponse:
    project = get_visible_project(request.user, project_uuid)
    run = get_object_or_404(AnalysisRun, uuid=run_uuid, project=project)
    if not can_view_run(request.user, project, run):
        raise Http404("Запуск не найден")
    sort = request.GET.get("sort", "-total_score")
    allowed = {
        "total_score",
        "-total_score",
        "internal_score",
        "-internal_score",
        "k",
        "-k",
        "silhouette",
        "-silhouette",
    }
    if sort not in allowed:
        sort = "-total_score"
    candidates = run.candidates.all().order_by(sort, "-id")
    return render(
        request,
        "analytics/candidates.html",
        {"project": project, "run": run, "candidates": candidates, "sort": sort},
    )


@login_required
@require_http_methods(["GET", "POST"])
def candidate_detail(request: HttpRequest, project_uuid, run_uuid, candidate_id: int) -> HttpResponse:
    project = get_visible_project(request.user, project_uuid)
    run = get_object_or_404(AnalysisRun, uuid=run_uuid, project=project)
    if not can_view_run(request.user, project, run):
        raise Http404("Запуск не найден")
    candidate = get_object_or_404(ModelCandidate, pk=candidate_id, run=run)
    if request.method == "POST":
        require_project_role(request.user, project, ProjectMembership.Role.ANALYST)
        if request.POST.get("select"):
            select_candidate(user=request.user, run=run, candidate=candidate, request=request)
        if request.POST.get("publish"):
            select_candidate(user=request.user, run=run, candidate=candidate, request=request)
            publish_run(user=request.user, run=run, request=request)
        return redirect("projects:candidate_detail", project_uuid=project.uuid, run_uuid=run.uuid, candidate_id=candidate.id)
    assignments = candidate.assignments.select_related("record").order_by("cluster_id", "record__territory_code")
    profiles = candidate.profiles.order_by("cluster_id")
    return render(
        request,
        "analytics/candidate.html",
        {
            "project": project,
            "run": run,
            "candidate": candidate,
            "assignments": assignments,
            "profiles": profiles,
            "n_used": candidate.n_used,
            "n_excluded": candidate.n_excluded,
        },
    )


@login_required
@require_GET
def run_passport(request: HttpRequest, project_uuid, run_uuid) -> HttpResponse:
    project = get_visible_project(request.user, project_uuid)
    run = get_object_or_404(AnalysisRun, uuid=run_uuid, project=project)
    if not can_view_run(request.user, project, run):
        raise Http404("Запуск не найден")
    return render(request, "analytics/passport.html", {"project": project, "run": run})


@login_required
@require_GET
def run_status_api(request: HttpRequest, run_uuid) -> JsonResponse:
    run = get_object_or_404(AnalysisRun, uuid=run_uuid)
    project = get_visible_project(request.user, run.project.uuid)
    if not can_view_run(request.user, project, run):
        raise Http404("Запуск не найден")
    return JsonResponse(
        {
            "uuid": str(run.uuid),
            "status": run.status,
            "progress": run.progress,
            "message": run.progress_message,
            "error": run.error_message,
        }
    )


@login_required
@require_GET
def candidate_chart_api(request: HttpRequest, candidate_id: int, kind: str) -> JsonResponse:
    candidate = get_object_or_404(ModelCandidate, pk=candidate_id)
    run = candidate.run
    project = get_visible_project(request.user, run.project.uuid)
    if not can_view_run(request.user, project, run):
        raise Http404("Запуск не найден")
    if kind == "boxplot":
        data = candidate.boxplot
    elif kind == "silhouette":
        data = {
            "labels": candidate.labels,
            "samples": candidate.silhouette_samples,
        }
    elif kind == "tik":
        data = candidate.tik_distribution
    else:
        raise Http404("График не найден")
    return JsonResponse(
        {
            "kind": kind,
            "n_used": candidate.n_used,
            "n_excluded": candidate.n_excluded,
            "denominator": "УИК, прошедшие отбор признаков",
            "disclaimer": "Кластеризация описывает статистические профили участков и не устанавливает причин и нарушений.",
            "data": data,
        }
    )


@login_required
@require_GET
def export_view(request: HttpRequest, project_uuid, run_uuid, kind: str) -> HttpResponse:
    project = get_visible_project(request.user, project_uuid)
    run = get_object_or_404(AnalysisRun, uuid=run_uuid, project=project)
    if not can_view_run(request.user, project, run):
        raise Http404("Запуск не найден")
    require_project_role(request.user, project, ProjectMembership.Role.ANALYST, ProjectMembership.Role.VIEWER)
    if kind == "csv":
        return export_assignments_csv(request.user, run, request)
    if kind == "xlsx":
        return export_assignments_xlsx(request.user, run, request)
    if kind == "json":
        return export_passport_json(request.user, run, request)
    if kind == "html":
        return export_report_html(request.user, run, request)
    if kind == "pdf":
        return export_report_pdf(request.user, run, request)
    raise Http404("Экспорт не найден")
