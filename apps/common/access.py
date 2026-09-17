from __future__ import annotations

from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.shortcuts import get_object_or_404

from apps.accounts.models import User
from apps.projects.models import Project, ProjectMembership

POLICY = (
    "Чужой объект скрывается ответом 404. Недостаток прав у члена проекта — 403."
)


def project_membership(user: User, project: Project) -> ProjectMembership | None:
    if not user.is_authenticated:
        return None
    if user.is_system_admin:
        membership = project.memberships.filter(user=user).first()
        if membership:
            return membership
        return ProjectMembership(project=project, user=user, role=ProjectMembership.Role.ANALYST)
    return project.memberships.filter(user=user).first()


def get_visible_project(user: User, project_uuid) -> Project:
    project = get_object_or_404(Project, uuid=project_uuid)
    membership = project_membership(user, project)
    if membership is None:
        raise Http404("Проект не найден")
    return project


def require_project_role(user: User, project: Project, *roles: str) -> ProjectMembership:
    membership = project_membership(user, project)
    if membership is None:
        raise Http404("Проект не найден")
    if user.is_system_admin:
        return membership
    if membership.role not in roles:
        raise PermissionDenied("Недостаточно прав для этого действия")
    return membership


def can_view_run(user: User, project: Project, run) -> bool:
    membership = project_membership(user, project)
    if membership is None:
        return False
    if user.is_system_admin or membership.role == ProjectMembership.Role.ANALYST:
        return True
    return bool(run.published_at)
