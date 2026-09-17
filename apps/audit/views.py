from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET

from apps.audit.models import AuditEvent
from apps.common.access import get_visible_project, require_project_role
from apps.projects.models import ProjectMembership


@login_required
@require_GET
def audit_list(request: HttpRequest, project_uuid) -> HttpResponse:
    project = get_visible_project(request.user, project_uuid)
    if request.user.is_system_admin:
        events = AuditEvent.objects.filter(project=project).select_related("actor")[:500]
    else:
        require_project_role(request.user, project, ProjectMembership.Role.ANALYST)
        events = AuditEvent.objects.filter(project=project).select_related("actor")[:500]
    return render(request, "audit/list.html", {"project": project, "events": events})
