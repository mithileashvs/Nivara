import re
from typing import Annotated, Any
from uuid import UUID

from fastapi import Path
from pydantic import StringConstraints

from app.core.errors import BadRequestError

# Supports UUID strings (36 chars with hyphens or 32 hex) as well as 24 hex chars
ID_PATTERN = r"^[0-9a-fA-F-]{24,36}$"

# Body / query fields: validated by Pydantic -> 422 on failure.
ObjectIdStr = Annotated[str, StringConstraints(pattern=ID_PATTERN)]
# Path parameters: same validation, appears nicely in OpenAPI.
ObjectIdPath = Annotated[str, Path(pattern=ID_PATTERN, description="Unique Identifier (UUID or hex)")]


def oid(value: Any) -> str:
    """Validate and return normalized string ID."""
    if not value:
        raise BadRequestError("Invalid identifier", code="invalid_id")
    s = str(value).strip()
    if not re.match(ID_PATTERN, s):
        raise BadRequestError("Invalid identifier", code="invalid_id")
    return s


def oids(values: list[Any] | None) -> list[str]:
    return [oid(v) for v in (values or [])]
