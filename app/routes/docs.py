"""OpenAPI helpers: consistent error response documentation."""
from typing import Any

from app.schemas.common import ErrorResponse

_DESC = {
    400: "Bad request — the request is well-formed but not acceptable (e.g. invalid date range)",
    401: "Unauthorized — missing, invalid or expired bearer token",
    403: "Forbidden — authenticated but not allowed to perform this action",
    404: "Not found",
    409: "Conflict — the action conflicts with current state (e.g. slot already taken, intake closed)",
    422: "Validation error — request body/query/path failed validation",
    429: "Too many requests — rate limit exceeded",
}


def errs(*codes: int) -> dict[int | str, dict[str, Any]]:
    return {c: {"model": ErrorResponse, "description": _DESC[c]} for c in codes}


AUTHED = errs(401, 403)
AUTH_DESC = "**Auth:** Bearer token required."
