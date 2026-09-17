from __future__ import annotations

from apps.audit.models import AuditEvent


def log_event(
    actor,
    action: str,
    *,
    project=None,
    object_uuid: str = "",
    object_type: str = "",
    request=None,
    extra: dict | None = None,
) -> AuditEvent:
    ip = None
    user_agent = ""
    correlation_id = ""
    if request is not None:
        ip = _client_ip(request)
        user_agent = request.META.get("HTTP_USER_AGENT", "")[:1000]
        correlation_id = getattr(request, "correlation_id", "") or request.headers.get("X-Correlation-ID", "")
    return AuditEvent.objects.create(
        actor=actor if getattr(actor, "is_authenticated", False) else None,
        action=action,
        object_type=object_type,
        object_uuid=object_uuid,
        project=project,
        ip_address=ip,
        user_agent=user_agent,
        extra=extra or {},
        correlation_id=correlation_id,
    )


def _client_ip(request) -> str | None:
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")
