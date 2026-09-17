from __future__ import annotations

from django.db import transaction

from apps.accounts.models import User
from apps.audit.services import log_event
from apps.projects.models import Project, ProjectMembership


@transaction.atomic
def create_project(*, user: User, name: str, description: str = "", request=None) -> Project:
    project = Project.objects.create(name=name, description=description, created_by=user)
    ProjectMembership.objects.create(
        project=project,
        user=user,
        role=ProjectMembership.Role.ANALYST,
        created_by=user,
    )
    log_event(user, "project_create", project=project, object_uuid=str(project.uuid), request=request)
    return project


@transaction.atomic
def add_member(*, actor: User, project: Project, user: User, role: str, request=None) -> ProjectMembership:
    membership, created = ProjectMembership.objects.update_or_create(
        project=project,
        user=user,
        defaults={"role": role, "created_by": actor},
    )
    log_event(
        actor,
        "membership_change",
        project=project,
        object_uuid=str(project.uuid),
        request=request,
        extra={"target_user": user.username, "role": role, "created": created},
    )
    return membership


@transaction.atomic
def remove_member(*, actor: User, membership: ProjectMembership, request=None) -> None:
    project = membership.project
    extra = {"target_user": membership.user.username}
    membership.delete()
    log_event(actor, "membership_remove", project=project, object_uuid=str(project.uuid), request=request, extra=extra)
