from __future__ import annotations

from django.contrib import admin
from django.urls import include, path

from apps.analytics.views import healthcheck

urlpatterns = [
    path("health/", healthcheck, name="health"),
    path("admin/", admin.site.urls),
    path("accounts/", include("apps.accounts.urls")),
    path("api/", include("apps.analytics.api_urls")),
    path("", include("apps.projects.urls")),
]

handler400 = "apps.accounts.views.handler400"
handler403 = "apps.accounts.views.handler403"
handler404 = "apps.accounts.views.handler404"
handler500 = "apps.accounts.views.handler500"
