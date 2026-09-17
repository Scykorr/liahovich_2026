from __future__ import annotations

import csv
import json
from io import BytesIO, StringIO

from django.core.files.base import ContentFile
from django.http import HttpResponse
from django.template.loader import render_to_string
from fpdf import FPDF
from openpyxl import Workbook

from apps.analytics.models import AnalysisRun, Artifact
from apps.audit.services import log_event


def _safe_csv_value(value: object) -> str:
    text = "" if value is None else str(value)
    if text[:1] in {"=", "+", "-", "@"}:
        return f"'{text}"
    return text


def _filename(run: AnalysisRun, suffix: str) -> str:
    return f"liahovich_{run.uuid}_{suffix}"


def export_assignments_csv(user, run: AnalysisRun, request=None) -> HttpResponse:
    candidate = run.selected_candidate or run.recommended_candidate
    buffer = StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        ["territory_code", "precinct_code", "cluster_id", "distance_to_center"]
    )
    if candidate:
        for item in candidate.assignments.select_related("record"):
            writer.writerow(
                [
                    _safe_csv_value(item.record.territory_code),
                    _safe_csv_value(item.record.precinct_code),
                    item.cluster_id,
                    f"{item.distance_to_center:.6f}",
                ]
            )
    payload = buffer.getvalue()
    _store_artifact(run, candidate, Artifact.Kind.EXPORT_CSV, _filename(run, "assignments.csv"), payload.encode("utf-8"))
    log_event(user, "export_csv", project=run.project, object_uuid=str(run.uuid), request=request)
    response = HttpResponse(payload, content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{_filename(run, "assignments.csv")}"'
    return response


def export_assignments_xlsx(user, run: AnalysisRun, request=None) -> HttpResponse:
    candidate = run.selected_candidate or run.recommended_candidate
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "assignments"
    sheet.append(["territory_code", "precinct_code", "cluster_id", "distance_to_center"])
    if candidate:
        for item in candidate.assignments.select_related("record"):
            sheet.append(
                [
                    _safe_csv_value(item.record.territory_code),
                    _safe_csv_value(item.record.precinct_code),
                    item.cluster_id,
                    float(item.distance_to_center),
                ]
            )
    output = BytesIO()
    workbook.save(output)
    payload = output.getvalue()
    _store_artifact(run, candidate, Artifact.Kind.EXPORT_XLSX, _filename(run, "assignments.xlsx"), payload)
    log_event(user, "export_xlsx", project=run.project, object_uuid=str(run.uuid), request=request)
    response = HttpResponse(
        payload,
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = f'attachment; filename="{_filename(run, "assignments.xlsx")}"'
    return response


def export_passport_json(user, run: AnalysisRun, request=None) -> HttpResponse:
    payload = {
        "run_uuid": str(run.uuid),
        "dataset_uuid": str(run.dataset.uuid),
        "dataset_sha256": run.dataset.sha256,
        "dataset_schema": run.dataset.schema_json,
        "seed": run.seed,
        "config": run.config_json,
        "library_versions": run.library_versions,
        "status": run.status,
        "n_used": run.n_used,
        "n_excluded": run.n_excluded,
        "recommended_candidate_id": run.recommended_candidate_id,
        "selected_candidate_id": run.selected_candidate_id,
        "created_at": run.created_at.isoformat(),
    }
    raw = json.dumps(payload, ensure_ascii=False, indent=2)
    _store_artifact(run, run.selected_candidate, Artifact.Kind.EXPORT_JSON, _filename(run, "passport.json"), raw.encode("utf-8"))
    log_event(user, "export_json", project=run.project, object_uuid=str(run.uuid), request=request)
    response = HttpResponse(raw, content_type="application/json; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{_filename(run, "passport.json")}"'
    return response


def export_report_html(user, run: AnalysisRun, request=None) -> HttpResponse:
    html = render_to_string(
        "reports/summary.html",
        {"run": run, "project": run.project, "candidate": run.selected_candidate or run.recommended_candidate},
    )
    _store_artifact(run, run.selected_candidate, Artifact.Kind.REPORT_HTML, _filename(run, "report.html"), html.encode("utf-8"))
    log_event(user, "export_html", project=run.project, object_uuid=str(run.uuid), request=request)
    response = HttpResponse(html, content_type="text/html; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{_filename(run, "report.html")}"'
    return response


def export_report_pdf(user, run: AnalysisRun, request=None) -> HttpResponse:
    candidate = run.selected_candidate or run.recommended_candidate
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=10)
    lines = [
        f"Pasport zapuska {run.uuid}",
        f"Seed: {run.seed}",
        f"Status: {run.status}",
        f"N used: {run.n_used}, excluded: {run.n_excluded}",
        "Klasterizaciya opisyvaet statisticheskie profili i ne ustanavlivaet prichin i narusheniy.",
    ]
    if candidate:
        lines.append(f"k={candidate.k} features={candidate.features} score={candidate.total_score}")
    width = pdf.epw
    for line in lines:
        safe = str(line).encode("ascii", "replace").decode("ascii")
        pdf.multi_cell(width, 7, safe)
        pdf.ln(1)
    payload = bytes(pdf.output())
    payload = bytes(pdf.output())
    _store_artifact(run, candidate, Artifact.Kind.REPORT_PDF, _filename(run, "report.pdf"), payload)
    log_event(user, "export_pdf", project=run.project, object_uuid=str(run.uuid), request=request)
    response = HttpResponse(payload, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{_filename(run, "report.pdf")}"'
    return response


def _store_artifact(run, candidate, kind, filename: str, payload: bytes) -> Artifact:
    artifact = Artifact(run=run, candidate=candidate, kind=kind, created_by=run.created_by)
    artifact.file.save(filename, ContentFile(payload), save=True)
    return artifact
