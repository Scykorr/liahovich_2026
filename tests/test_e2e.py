from __future__ import annotations

import pytest
from django.urls import reverse

from analytics_core.types import PipelineConfig
from apps.analytics.models import AnalysisRun
from apps.analytics.services import create_run, execute_run, publish_run, queue_run
from apps.datasets.services import import_records, save_mapping, upload_dataset
from apps.projects.models import ProjectMembership
from apps.reports.services import export_assignments_csv, export_passport_json


def _prepare_dataset(analyst, project, valid_csv_file):
    dataset = upload_dataset(user=analyst, project=project, uploaded_file=valid_csv_file)
    save_mapping(
        user=analyst,
        dataset=dataset,
        mapping={
            "territory_code": "ТИК",
            "precinct_code": "УИК",
            "registered_voters": "Избиратели",
            "ballots_in_boxes": "Бюллетени",
            "outside_ballots": "Вне участка",
            "valid_ballots": "Действительные",
            "invalid_ballots": "Недействительные",
        },
        candidate_columns={"candidate_1": "Кандидат А", "candidate_2": "Кандидат Б"},
        encoding="utf-8",
        delimiter=";",
    )
    import_records(user=analyst, dataset=dataset)
    return dataset


@pytest.mark.django_db
def test_full_flow_eager_celery(client, analyst, viewer, project, valid_csv_file) -> None:
    dataset = _prepare_dataset(analyst, project, valid_csv_file)
    config = PipelineConfig(
        seed=3,
        k_min=2,
        k_max=3,
        feature_combo_min=2,
        feature_combo_max=2,
        bootstrap_repeats=5,
        bootstrap_top_n=2,
        n_init=20,
    )
    run = create_run(user=analyst, dataset=dataset, config=config)
    queue_run(user=analyst, run=run)
    run.refresh_from_db()
    assert run.status == AnalysisRun.Status.SUCCEEDED
    assert run.candidates.exists()
    assert run.selected_candidate_id
    publish_run(user=analyst, run=run)
    csv_response = export_assignments_csv(analyst, run)
    assert csv_response.status_code == 200
    assert "territory_code" in csv_response.content.decode()
    json_response = export_passport_json(analyst, run)
    assert b"library_versions" in json_response.content

    ProjectMembership.objects.create(project=project, user=viewer, role=ProjectMembership.Role.VIEWER)
    client.force_login(viewer)
    published = client.get(reverse("projects:run_candidates", args=[project.uuid, run.uuid]))
    assert published.status_code == 200

    draft = create_run(user=analyst, dataset=dataset, config=config)
    hidden = client.get(reverse("projects:run_progress", args=[project.uuid, draft.uuid]))
    assert hidden.status_code == 404


@pytest.mark.django_db
def test_same_seed_reproduces(analyst, project, valid_csv_file) -> None:
    dataset = _prepare_dataset(analyst, project, valid_csv_file)
    config = PipelineConfig(
        seed=21,
        k_min=2,
        k_max=2,
        feature_combo_min=2,
        feature_combo_max=2,
        bootstrap_repeats=4,
        bootstrap_top_n=1,
        n_init=20,
    )
    run_a = create_run(user=analyst, dataset=dataset, config=config)
    execute_run(str(run_a.uuid))
    run_b = create_run(user=analyst, dataset=dataset, config=config)
    execute_run(str(run_b.uuid))
    cand_a = run_a.candidates.order_by("id").first()
    cand_b = run_b.candidates.order_by("id").first()
    assert cand_a.labels == cand_b.labels
    assert cand_a.total_score == cand_b.total_score
