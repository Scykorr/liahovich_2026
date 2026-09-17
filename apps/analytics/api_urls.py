from django.urls import path

from apps.analytics.views import candidate_chart_api, run_status_api

urlpatterns = [
    path("runs/<uuid:run_uuid>/status/", run_status_api, name="run_status"),
    path("candidates/<int:candidate_id>/charts/<str:kind>/", candidate_chart_api, name="candidate_chart"),
]
