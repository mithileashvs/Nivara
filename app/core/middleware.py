import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.core.audit_context import (
    clear_audit_actor,
    extract_client_ip,
    extract_user_agent,
    reset_request_meta,
    set_request_meta,
)

logger = logging.getLogger("smartcare.access")


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Adds a request id, basic security headers, audit context, and access logging."""

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex[:16]
        request.state.request_id = request_id
        app_state = getattr(getattr(request, "app", None), "state", None)
        settings = getattr(app_state, "settings", None)
        token = set_request_meta({
            "ip_address": extract_client_ip(request, settings=settings),
            "user_agent": extract_user_agent(request),
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
        })
        clear_audit_actor()
        started = time.perf_counter()
        try:
            response = await call_next(request)
        finally:
            clear_audit_actor()
            reset_request_meta(token)
        elapsed_ms = (time.perf_counter() - started) * 1000
        response.headers["X-Request-ID"] = request_id
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        if request.url.path.startswith("/api/"):
            response.headers.setdefault("Cache-Control", "no-store")
        logger.info(
            "%s %s -> %s (%.1f ms) rid=%s",
            request.method, request.url.path, response.status_code, elapsed_ms, request_id,
        )
        return response
