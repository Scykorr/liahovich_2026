from __future__ import annotations

import pytest

from analytics_core.types import PipelineConfig
from apps.analytics.services import create_run, execute_run
from apps.reports.services import _safe_csv_value, export_assignments_csv
from tests.test_e2e import _prepare_dataset


def test_formula_injection_prefix() -> None:
    assert _safe_csv_value("=cmd") == "'=cmd"
    assert _safe_csv_value("+1") == "'+1"
    assert _safe_csv_value("-1") == "'-1"
    assert _safe_csv_value("@sum") == "'@sum"
    assert _safe_csv_value("0100") == "0100"


@pytest.mark.django_db
def test_export_csv_protected(analyst, project, valid_csv_file) -> None:
    dataset = _prepare_dataset(analyst, project, valid_csv_file)
    run = create_run(
        user=analyst,
        dataset=dataset,
        config=PipelineConfig(
            seed=1, k_min=2, k_max=2, feature_combo_min=2, feature_combo_max=2, bootstrap_repeats=3, bootstrap_top_n=1
        ),
    )
    execute_run(str(run.uuid))
    response = export_assignments_csv(analyst, run)
    body = response.content.decode()
    assert "Content-Disposition" in response.headers
    assert "liahovich_" in response.headers["Content-Disposition"]
    assert body.splitlines()[0].startswith("territory_code")
