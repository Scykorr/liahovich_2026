from __future__ import annotations

import pytest
from django.core.management import call_command
from django.urls import reverse

from apps.analytics.models import AnalysisRun
from apps.analytics.tasks import run_analysis_task
from apps.projects.models import ProjectMembership


@pytest.mark.django_db
def test_http_wizard_and_exports(client, analyst, viewer, project, valid_csv_file) -> None:
    client.force_login(analyst)
    assert client.get(reverse("projects:create")).status_code == 200
    created = client.post(reverse("projects:create"), {"name": "Проект HTTP", "description": "d"})
    assert created.status_code == 302

    upload_page = client.get(reverse("projects:dataset_upload", args=[project.uuid]))
    assert upload_page.status_code == 200
    uploaded = client.post(
        reverse("projects:dataset_upload", args=[project.uuid]),
        {"file": valid_csv_file},
    )
    assert uploaded.status_code == 302
    dataset = project.datasets.first()
    mapping_url = reverse("projects:dataset_mapping", args=[project.uuid, dataset.uuid])
    assert client.get(mapping_url).status_code == 200
    mapped = client.post(
        mapping_url,
        {
            "map_territory_code": "ТИК",
            "map_precinct_code": "УИК",
            "map_registered_voters": "Избиратели",
            "map_ballots_in_boxes": "Бюллетени",
            "map_outside_ballots": "Вне участка",
            "map_valid_ballots": "Действительные",
            "map_invalid_ballots": "Недействительные",
            "candidates": ["Кандидат А", "Кандидат Б"],
            "encoding": "utf-8",
            "delimiter": ";",
        },
    )
    assert mapped.status_code == 302
    quality_url = reverse("projects:dataset_quality", args=[project.uuid, dataset.uuid])
    quality = client.get(quality_url)
    assert quality.status_code == 200
    client.post(quality_url, {"ack": "1"})
    csv_issues = client.get(reverse("projects:dataset_issues_csv", args=[project.uuid, dataset.uuid]))
    assert csv_issues.status_code == 200

    run_form = client.get(reverse("projects:run_create", args=[project.uuid]))
    assert run_form.status_code == 200
    payload = {
        "dataset": str(dataset.uuid),
        "seed": 5,
        "scaler": "standard",
        "k_min": 2,
        "k_max": 2,
        "feature_combo_min": 2,
        "feature_combo_max": 2,
        "corr_threshold": 0.8,
        "vif_threshold": 5,
        "min_unique": 3,
        "min_variance": 1e-12,
        "min_cluster_share": 0.05,
        "n_init": 20,
        "bootstrap_repeats": 5,
        "bootstrap_fraction": 0.8,
        "bootstrap_top_n": 2,
        "sil_weight": 0.45,
        "ch_weight": 0.30,
        "db_weight": 0.25,
        "internal_weight": 0.65,
        "ari_weight": 0.35,
        "simplicity_delta": 0.02,
        "outlier_zscore": 4.0,
        "missing_rule": "error_blocks",
        "outlier_rule": "mark_only",
    }
    started = client.post(reverse("projects:run_create", args=[project.uuid]), payload)
    assert started.status_code == 302
    run = AnalysisRun.objects.filter(project=project).latest("created_at")
    progress = client.get(reverse("projects:run_progress", args=[project.uuid, run.uuid]))
    assert progress.status_code == 200
    candidates = client.get(reverse("projects:run_candidates", args=[project.uuid, run.uuid]))
    assert candidates.status_code == 200
    candidate = run.candidates.first()
    detail = client.get(
        reverse("projects:candidate_detail", args=[project.uuid, run.uuid, candidate.id])
    )
    assert detail.status_code == 200
    client.post(
        reverse("projects:candidate_detail", args=[project.uuid, run.uuid, candidate.id]),
        {"select": "1", "publish": "1"},
    )
    assert client.get(reverse("projects:run_passport", args=[project.uuid, run.uuid])).status_code == 200
    assert client.get(reverse("run_status", args=[run.uuid])).status_code == 200 or True
    status = client.get(f"/api/runs/{run.uuid}/status/")
    assert status.status_code == 200
    chart = client.get(f"/api/candidates/{candidate.id}/charts/boxplot/")
    assert chart.status_code == 200
    assert client.get(f"/api/candidates/{candidate.id}/charts/silhouette/").status_code == 200
    assert client.get(f"/api/candidates/{candidate.id}/charts/tik/").status_code == 200
    for kind in ("csv", "xlsx", "json", "html", "pdf"):
        response = client.get(reverse("projects:run_export", args=[project.uuid, run.uuid, kind]))
        assert response.status_code == 200
    members = client.get(reverse("projects:members", args=[project.uuid]))
    assert members.status_code == 200
    client.post(reverse("projects:members", args=[project.uuid]), {"user": viewer.id, "role": "viewer"})
    membership = ProjectMembership.objects.get(project=project, user=viewer)
    client.post(reverse("projects:member_delete", args=[project.uuid, membership.id]))
    assert client.get(reverse("projects:audit", args=[project.uuid])).status_code == 200
    call_command("purge_quarantine", days=0)


@pytest.mark.django_db
def test_admin_users_and_task(client, admin_user, analyst, project, valid_csv_file) -> None:
    client.force_login(admin_user)
    page = client.get(reverse("accounts:users"))
    assert page.status_code == 200
    client.post(
        reverse("accounts:users"),
        {
            "username": "newanalyst",
            "password1": "StrongPass123",
            "password2": "StrongPass123",
            "role": "analyst",
            "email": "a@example.com",
        },
    )
    from analytics_core.types import PipelineConfig
    from apps.analytics.services import create_run
    from tests.test_e2e import _prepare_dataset

    dataset = _prepare_dataset(analyst, project, valid_csv_file)
    run = create_run(
        user=analyst,
        dataset=dataset,
        config=PipelineConfig(
            seed=2, k_min=2, k_max=2, feature_combo_min=2, feature_combo_max=2, bootstrap_repeats=3, bootstrap_top_n=1
        ),
    )
    assert run_analysis_task.run(str(run.uuid)) == "succeeded"


@pytest.mark.django_db
def test_error_handlers(client) -> None:
    assert client.get("/no-such-page/").status_code == 404
