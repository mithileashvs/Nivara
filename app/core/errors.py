"""Consistent, structured API errors.

Every error response has the same shape::

    {"error": {"code": "slot_unavailable", "message": "...", "details": ...}, "request_id": "..."}
"""
import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("smartcare.errors")


class AppError(Exception):
    status_code: int = 500
    default_code: str = "internal_error"

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        details: Any = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code or self.default_code
        self.details = details
        self.headers = headers


class BadRequestError(AppError):
    status_code = 400
    default_code = "bad_request"


class UnauthorizedError(AppError):
    status_code = 401
    default_code = "unauthorized"

    def __init__(self, message: str = "Authentication required", **kw: Any) -> None:
        kw.setdefault("headers", {"WWW-Authenticate": "Bearer"})
        super().__init__(message, **kw)


class ForbiddenError(AppError):
    status_code = 403
    default_code = "forbidden"


class NotFoundError(AppError):
    status_code = 404
    default_code = "not_found"


class ConflictError(AppError):
    status_code = 409
    default_code = "conflict"


class ValidationFailedError(AppError):
    status_code = 422
    default_code = "validation_error"


class TooManyRequestsError(AppError):
    status_code = 429
    default_code = "rate_limited"


def _body(request: Request, code: str, message: str, details: Any = None) -> dict[str, Any]:
    payload: dict[str, Any] = {"error": {"code": code, "message": message}}
    if details is not None:
        payload["error"]["details"] = details
    payload["request_id"] = getattr(request.state, "request_id", None)
    return payload


def _resolve_hospital_id_from_path(path: str) -> str | None:
    """Best-effort extract UUID after `/hospitals/{id}` for scoped security telemetry."""
    parts = [p for p in path.split("/") if p]
    for idx, seg in enumerate(parts):
        if seg == "hospitals" and idx + 1 < len(parts):
            candidate = parts[idx + 1]
            if len(candidate) in (32, 36):
                return candidate
    return None


async def _audit_security_error(request: Request, exc: AppError) -> None:
    from app.core.audit_context import get_audit_actor, is_inside_audit

    if is_inside_audit():
        return
    if exc.status_code not in (401, 403) or exc.code == "invalid_credentials":
        return

    path = request.url.path or ""
    if exc.status_code == 401:
        sensitive_prefix = any(
            path.startswith(prefix)
            for prefix in ("/api/v1/admin", "/api/v1/analytics", "/api/v1/medical-records")
        )
        if exc.code != "invalid_token" and not sensitive_prefix:
            return

    db = getattr(getattr(request, "app", None), "state", None)
    db = getattr(db, "db", None)
    settings = getattr(getattr(getattr(request, "app", None), "state", None), "settings", None)
    if db is None or settings is None:
        return

    try:
        from app.models.enums import AuditAction, AuditActorRole, AuditEntityType, AuditSeverity
        from app.services.audit_service import AuditService

        actor = get_audit_actor() or {}
        action = (
            AuditAction.AUTH_FORBIDDEN_ACCESS
            if exc.status_code == 403
            else AuditAction.AUTH_UNAUTHORIZED_ACCESS
        )
        hospital_id = _resolve_hospital_id_from_path(path)
        await AuditService(db, settings).log_event(
            action=action,
            entity_type=AuditEntityType.AUTH,
            entity_id=actor.get("user_id"),
            actor_id=actor.get("user_id"),
            actor_role=actor.get("role") or AuditActorRole.ANONYMOUS.value,
            hospital_id=hospital_id,
            severity=AuditSeverity.WARNING,
            description=f"{request.method} {path} denied ({exc.status_code}: {exc.code})",
            metadata={"method": request.method, "path": path, "error_code": exc.code, "status_code": exc.status_code},
            check_security_thresholds=True,
        )
    except Exception:  # noqa: BLE001
        logger.debug("Security audit hook skipped for %s", path)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(request: Request, exc: AppError) -> JSONResponse:
        await _audit_security_error(request, exc)
        return JSONResponse(
            status_code=exc.status_code,
            content=_body(request, exc.code, exc.message, exc.details),
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        # Only expose location / message / type — never echo raw input (may contain secrets).
        details = [
            {"loc": [str(p) for p in err.get("loc", [])], "message": err.get("msg"), "type": err.get("type")}
            for err in exc.errors()
        ]
        return JSONResponse(
            status_code=422,
            content=_body(request, "validation_error", "Request validation failed", details),
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = {404: "not_found", 405: "method_not_allowed"}.get(exc.status_code, "http_error")
        return JSONResponse(
            status_code=exc.status_code,
            content=_body(request, code, str(exc.detail)),
            headers=getattr(exc, "headers", None),
        )

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=500,
            content=_body(request, "internal_error", "An unexpected error occurred"),
        )
