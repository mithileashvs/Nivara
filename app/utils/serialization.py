"""Database row / dict -> API dict conversion."""
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

# Fields that must never leave the service layer.
_HIDDEN_KEYS = {"password_hash"}


def to_api(value: Any) -> Any:
    """Recursively convert `_id` -> `id`, UUID -> str, and drop hidden keys."""
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for key, val in value.items():
            if key in _HIDDEN_KEYS:
                continue
            out["id" if key == "_id" else key] = to_api(val)
        return out
    if isinstance(value, list):
        return [to_api(v) for v in value]
    if isinstance(value, UUID):
        return str(value)
    if hasattr(value, "__class__") and value.__class__.__name__ == "ObjectId":
        return str(value)
    if isinstance(value, datetime) and value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value
