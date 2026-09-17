from __future__ import annotations


def user_role(request) -> dict[str, object]:
    user = getattr(request, "user", None)
    return {
        "user_is_admin": bool(user and user.is_authenticated and user.is_system_admin),
    }
