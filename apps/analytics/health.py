from __future__ import annotations

from django.core.cache import cache
from django.db import connection
from django.http import HttpRequest, JsonResponse
from django.views.decorators.http import require_GET


@require_GET
def healthcheck(request: HttpRequest) -> JsonResponse:
    db_ok = True
    redis_ok = True
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except Exception:  # noqa: BLE001
        db_ok = False
    try:
        cache.set("health", "ok", 5)
        redis_ok = cache.get("health") == "ok"
    except Exception:  # noqa: BLE001
        redis_ok = False
    status = 200 if db_ok else 503
    return JsonResponse({"status": "ok" if db_ok else "degraded", "database": db_ok, "cache": redis_ok}, status=status)
