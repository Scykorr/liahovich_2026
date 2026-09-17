from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from apps.accounts.models import User
from apps.common.access import get_visible_project, require_project_role
from apps.projects.forms import MembershipForm, ProjectForm
from apps.projects.models import ProjectMembership
from apps.projects.services import add_member, create_project, remove_member


@login_required
@require_http_methods(["GET"])
def dashboard(request: HttpRequest) -> HttpResponse:
    projects = request.user.visible_projects().prefetch_related("memberships")
    return render(request, "projects/dashboard.html", {"projects": projects})


@login_required
@require_http_methods(["GET", "POST"])
def project_create(request: HttpRequest) -> HttpResponse:
    if request.user.role == User.Role.VIEWER and not request.user.is_system_admin:
        return render(request, "errors/403.html", status=403)
    form = ProjectForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        project = create_project(
            user=request.user,
            name=form.cleaned_data["name"],
            description=form.cleaned_data["description"],
            request=request,
        )
        return redirect("projects:detail", project_uuid=project.uuid)
    return render(request, "projects/form.html", {"form": form})


@login_required
@require_http_methods(["GET"])
def project_detail(request: HttpRequest, project_uuid) -> HttpResponse:
    project = get_visible_project(request.user, project_uuid)
    datasets = project.datasets.select_related("created_by").order_by("-version")
    runs = project.analysis_runs.select_related("dataset", "created_by").order_by("-created_at")[:20]
    membership = project.memberships.select_related("user")
    return render(
        request,
        "projects/detail.html",
        {"project": project, "datasets": datasets, "runs": runs, "memberships": membership},
    )


@login_required
@require_http_methods(["GET", "POST"])
def project_members(request: HttpRequest, project_uuid) -> HttpResponse:
    project = get_visible_project(request.user, project_uuid)
    require_project_role(request.user, project, ProjectMembership.Role.ANALYST)
    form = MembershipForm(request.POST or None)
    form.fields["user"].queryset = User.objects.order_by("username")
    if request.method == "POST" and form.is_valid():
        add_member(
            actor=request.user,
            project=project,
            user=form.cleaned_data["user"],
            role=form.cleaned_data["role"],
            request=request,
        )
        return redirect("projects:members", project_uuid=project.uuid)
    memberships = project.memberships.select_related("user")
    return render(
        request,
        "projects/members.html",
        {"project": project, "form": form, "memberships": memberships},
    )


@login_required
@require_http_methods(["POST"])
def membership_delete(request: HttpRequest, project_uuid, membership_id: int) -> HttpResponse:
    project = get_visible_project(request.user, project_uuid)
    require_project_role(request.user, project, ProjectMembership.Role.ANALYST)
    membership = get_object_or_404(ProjectMembership, pk=membership_id, project=project)
    remove_member(actor=request.user, membership=membership, request=request)
    return redirect("projects:members", project_uuid=project.uuid)
