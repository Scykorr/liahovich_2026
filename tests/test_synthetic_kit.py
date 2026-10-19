from __future__ import annotations

import json

import pytest
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile

from analytics_core.pipeline import feature_combos, run_pipeline, synthetic_control_config
from analytics_core.ranking import internal_sort_key
from analytics_core.types import PrecinctRow
from apps.datasets.io import guess_candidates, guess_mapping, is_reference_label_file, read_tabular
from apps.datasets.services import import_records, records_to_core, save_mapping, upload_dataset
from apps.datasets.synthetic_kit import (
    DATA_NAME,
    LABELS_NAME,
    PASSPORT_NAME,
    SYNTHETIC_CANDIDATES,
    SYNTHETIC_MAPPING,
    kit_file,
    load_passport,
    verify_kit_hashes,
)

FEATURE_CODE = {
    "T": "turnout",
    "H": "outside",
    "I": "invalid",
    "B": "candidate_B",
    "C": "candidate_C",
    "D": "candidate_D",
}


def test_kit_files_match_passport_hashes() -> None:
    passport = load_passport()
    digests = verify_kit_hashes()
    assert passport["rows"] == 600
    assert passport["subset_count"] == 22
    assert passport["admissible_models"] == 109
    assert digests[DATA_NAME] == passport["files"][DATA_NAME]
    assert kit_file(PASSPORT_NAME).is_file()


def test_synthetic_columns_do_not_treat_metadata_as_candidates() -> None:
    columns, rows, _encoding, _delimiter = read_tabular(kit_file(DATA_NAME))
    assert "election_id" in columns
    assert len(rows) == 600
    mapping = guess_mapping(columns)
    candidates = guess_candidates(columns, mapping)
    assert "election_id" not in candidates
    assert candidates == ["candidate_A", "candidate_B", "candidate_C", "candidate_D"]
    label_columns, _label_rows, _encoding, _delimiter = read_tabular(kit_file(LABELS_NAME))
    assert is_reference_label_file(label_columns)
    assert guess_candidates(label_columns, guess_mapping(label_columns)) == []
    config = synthetic_control_config(subsample_repeats=0)
    assert len(feature_combos(list(config.selected_features or []), config)) == 22


def test_repository_search_matches_passport_internal_metrics() -> None:
    passport = load_passport()
    columns, rows, _encoding, _delimiter = read_tabular(kit_file(DATA_NAME))
    core_rows = _core_rows(columns, rows)
    result = run_pipeline(core_rows, synthetic_control_config(subsample_repeats=0))
    assert result.fixed_leader == "candidate_A"
    assert result.models_calculated == 110
    assert result.models_admissible == passport["admissible_models"]
    best = min(
        (item for item in result.candidates if not item.rejected and item.internal_score is not None),
        key=internal_sort_key,
    )
    expected = passport["top5"][0]
    assert best.features == [_decode_feature(part) for part in expected["features"].split("+")]
    assert best.k == expected["k"]
    assert best.silhouette == pytest.approx(expected["sil"], abs=1e-6)
    assert best.calinski_harabasz == pytest.approx(expected["ch"], abs=1e-4)
    assert best.davies_bouldin == pytest.approx(expected["db"], abs=1e-6)
    assert best.sizes and min(best.sizes.values()) == expected["smallest"]


def test_repository_stability_matches_passport_top_model() -> None:
    import numpy as np

    from analytics_core.clustering import fit_cluster_model
    from analytics_core.pipeline import build_feature_frame
    from analytics_core.stability import repeated_subsample_stability

    passport = load_passport()
    _columns, rows, _encoding, _delimiter = read_tabular(kit_file(DATA_NAME))
    frame = build_feature_frame(_core_rows(_columns, rows))
    matrix = frame[["turnout", "candidate_B"]].to_numpy(dtype=float)
    fitted = fit_cluster_model(matrix, k=3, scaler="standard", seed=20261019, n_init=20, silhouette_max_rows=0)
    report = repeated_subsample_stability(
        matrix,
        frame["territory_code"].to_numpy(),
        np.asarray(fitted["labels"]),
        k=3,
        scaler="standard",
        seed=20261019,
        n_init=20,
        repeats=100,
        fraction=0.80,
        column_positions=[0, 3],
    )
    expected = passport["top5"][0]
    assert report.successes == 100
    assert report.ari_mean == pytest.approx(expected["ari_mean"], abs=1e-6)
    assert report.ari_p10 == pytest.approx(expected["ari_p10"], abs=1e-6)
    assert report.ari_p90 == pytest.approx(expected["ari_p90"], abs=1e-6)
    assert report.ari_sd == pytest.approx(expected["ari_sd"], abs=1e-6)


@pytest.mark.django_db
def test_import_analyze_export_roundtrip(analyst, project) -> None:
    from apps.analytics.services import create_run, execute_run
    from apps.reports.services import export_assignments_csv, export_passport_json

    upload = SimpleUploadedFile("labels.csv", kit_file(LABELS_NAME).read_bytes(), content_type="text/csv")
    with pytest.raises(ValidationError):
        upload_dataset(user=analyst, project=project, uploaded_file=upload)

    dataset = upload_dataset(
        user=analyst,
        project=project,
        uploaded_file=SimpleUploadedFile(DATA_NAME, kit_file(DATA_NAME).read_bytes(), content_type="text/csv"),
    )
    save_mapping(
        user=analyst,
        dataset=dataset,
        mapping=SYNTHETIC_MAPPING,
        candidate_columns=SYNTHETIC_CANDIDATES,
        encoding="utf-8",
        delimiter=",",
    )
    import_records(user=analyst, dataset=dataset)
    dataset.refresh_from_db()
    assert dataset.issues.filter(level="error").count() == 0
    assert dataset.row_count == 600
    assert "election_id" not in dataset.column_mapping.candidate_columns
    rows = records_to_core(dataset)
    assert rows[0].candidate_votes.keys() == SYNTHETIC_CANDIDATES.keys()
    run = create_run(
        user=analyst,
        dataset=dataset,
        config=synthetic_control_config(subsample_repeats=1, subsample_top_n=1, k_min=3, k_max=3, n_init=20),
    )
    finished = execute_run(str(run.uuid))
    assert finished.status == "succeeded"
    assert finished.summary_json["models_calculated"] > 0
    assert finished.summary_json["fixed_leader"] == "candidate_A"
    passport = json.loads(export_passport_json(analyst, finished).content)
    assert passport["dataset_sha256"] == dataset.sha256
    assert passport["summary"]["subsample"] == "stratified_without_replacement"
    assert b"territory_code" in export_assignments_csv(analyst, finished).content


def _decode_feature(code: str) -> str:
    return FEATURE_CODE[code]


def _core_rows(_columns: list[str], rows: list[dict[str, str]]) -> list[PrecinctRow]:
    core_rows = []
    for index, row in enumerate(rows, start=2):
        votes = {name: int(row[column]) for name, column in SYNTHETIC_CANDIDATES.items()}
        core_rows.append(
            PrecinctRow(
                row_number=index,
                territory_code=row["territory_code"],
                precinct_code=row["precinct_code"],
                registered_voters=int(row["registered_voters"]),
                ballots_in_boxes=int(row["ballots_in_boxes"]),
                outside_ballots=int(row["outside_ballots"]),
                valid_ballots=int(row["valid_ballots"]),
                invalid_ballots=int(row["invalid_ballots"]),
                candidate_votes=votes,
            )
        )
    return core_rows
