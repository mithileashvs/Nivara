from datetime import date, datetime, time, timezone
from typing import Annotated, Any, Generic, TypeVar

from pydantic import AfterValidator, BaseModel, ConfigDict, Field

T = TypeVar("T")


def _as_utc(v: datetime) -> datetime:
    return v.replace(tzinfo=timezone.utc) if v.tzinfo is None else v


def _whole_minute(v: time) -> time:
    if v.second or v.microsecond:
        raise ValueError("time must be a whole minute (HH:MM)")
    return v


# Datetimes come out of MongoDB as naive UTC — always serialise with an explicit UTC offset.
UTCDateTime = Annotated[datetime, AfterValidator(_as_utc)]
# Clinic-local wall-clock time, whole minutes only.
WholeMinuteTime = Annotated[time, AfterValidator(_whole_minute)]


class RequestModel(BaseModel):
    """Base for request bodies: trims strings and rejects unknown fields."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")


class ResponseModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Page(BaseModel, Generic[T]):
    items: list[T]
    page: int = Field(description="1-based page number")
    page_size: int
    total: int = Field(description="Total items matching the query")
    total_pages: int


class ErrorDetail(BaseModel):
    code: str = Field(examples=["slot_unavailable"])
    message: str
    details: Any | None = None


class ErrorResponse(BaseModel):
    error: ErrorDetail
    request_id: str | None = None


class MessageResponse(BaseModel):
    message: str


def make_page(items: list[Any], total: int, page: int, page_size: int) -> dict[str, Any]:
    import math

    return {
        "items": items,
        "page": page,
        "page_size": page_size,
        "total": total,
        "total_pages": math.ceil(total / page_size) if total else 0,
    }


__all__ = [
    "UTCDateTime", "WholeMinuteTime", "RequestModel", "ResponseModel", "Page",
    "ErrorDetail", "ErrorResponse", "MessageResponse", "make_page", "date", "time",
]
