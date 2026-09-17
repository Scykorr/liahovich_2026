from django.urls import path

from apps.analytics import views
from apps.audit.views import audit_list
from apps.projects import views as project_views

app_name = "projects"

urlpatterns = [
    path("", project_views.dashboard, name="dashboard"),
    path("projects/new/", project_views.project_create, name="create"),
    path("projects/<uuid:project_uuid>/", project_views.project_detail, name="detail"),
    path("projects/<uuid:project_uuid>/members/", project_views.project_members, name="members"),
    path(
        "projects/<uuid:project_uuid>/members/<int:membership_id>/delete/",
        project_views.membership_delete,
        name="member_delete",
    ),
    path("projects/<uuid:project_uuid>/datasets/upload/", views.dataset_upload, name="dataset_upload"),
    path(
        "projects/<uuid:project_uuid>/datasets/<uuid:dataset_uuid>/mapping/",
        views.dataset_mapping,
        name="dataset_mapping",
    ),
    path(
        "projects/<uuid:project_uuid>/datasets/<uuid:dataset_uuid>/quality/",
        views.dataset_quality,
        name="dataset_quality",
    ),
    path(
        "projects/<uuid:project_uuid>/datasets/<uuid:dataset_uuid>/quality.csv",
        views.dataset_issues_csv,
        name="dataset_issues_csv",
    ),
    path("projects/<uuid:project_uuid>/runs/new/", views.run_create, name="run_create"),
    path("projects/<uuid:project_uuid>/runs/<uuid:run_uuid>/", views.run_progress, name="run_progress"),
    path(
        "projects/<uuid:project_uuid>/runs/<uuid:run_uuid>/candidates/",
        views.run_candidates,
        name="run_candidates",
    ),
    path(
        "projects/<uuid:project_uuid>/runs/<uuid:run_uuid>/candidates/<int:candidate_id>/",
        views.candidate_detail,
        name="candidate_detail",
    ),
    path("projects/<uuid:project_uuid>/runs/<uuid:run_uuid>/passport/", views.run_passport, name="run_passport"),
    path(
        "projects/<uuid:project_uuid>/runs/<uuid:run_uuid>/export/<str:kind>/",
        views.export_view,
        name="run_export",
    ),
    path("projects/<uuid:project_uuid>/audit/", audit_list, name="audit"),
]
