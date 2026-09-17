from __future__ import annotations

import logging
import uuid

from django.utils.deprecation import MiddlewareMixin

_correlation = logging.LoggerAdapter


class CorrelationIdMiddleware(MiddlewareMixin):
    def process_request(self, request):
        request.correlation_id = request.headers.get("X-Correlation-ID") or str(uuid.uuid4())

    def process_response(self, request, response):
        response["X-Correlation-ID"] = getattr(request, "correlation_id", "")
        return response


class RequestLogMiddleware(MiddlewareMixin):
    def process_response(self, request, response):
        logger = logging.getLogger("apps.audit")
        if request.path in {"/health/"}:
            return response
        logger.info(
            "request",
            extra={
                "correlation_id": getattr(request, "correlation_id", ""),
                "method": request.method,
                "path": request.path,
                "status": response.status_code,
                "user": getattr(getattr(request, "user", None), "username", ""),
            },
        )
        return response
