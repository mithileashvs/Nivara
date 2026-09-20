from typing import Annotated

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import Path
from pydantic import StringConstraints

from app.core.errors import BadRequestError

OID_PATTERN = r"^[0-9a-fA-F]{24}$"

# Body / query fields: 24-char hex string (validated by Pydantic -> 422 on failure).
ObjectIdStr = Annotated[str, StringConstraints(pattern=OID_PATTERN)]
# Path parameters: same validation, appears nicely in OpenAPI.
ObjectIdPath = Annotated[str, Path(pattern=OID_PATTERN, description="MongoDB ObjectId (24 hex chars)")]


def oid(value: str | ObjectId) -> ObjectId:
    if isinstance(value, ObjectId):
        return value
    try:
        return ObjectId(str(value))
    except (InvalidId, TypeError):
        raise BadRequestError("Invalid identifier", code="invalid_id") from None


def oids(values: list[str | ObjectId] | None) -> list[ObjectId]:
    return [oid(v) for v in (values or [])]
