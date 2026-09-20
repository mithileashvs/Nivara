import math
from dataclasses import dataclass
from typing import Any

from fastapi import Query

MAX_PAGE_SIZE = 100
DEFAULT_PAGE_SIZE = 20


@dataclass(frozen=True)
class PageParams:
    page: int
    page_size: int

    @property
    def skip(self) -> int:
        return (self.page - 1) * self.page_size


def page_params(
    page: int = Query(1, ge=1, le=100_000, description="1-based page number"),
    page_size: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE, description=f"Items per page (max {MAX_PAGE_SIZE})"),
) -> PageParams:
    return PageParams(page=page, page_size=page_size)


def total_pages(total: int, page_size: int) -> int:
    return math.ceil(total / page_size) if total else 0


async def paginate(
    collection: Any,
    query: dict[str, Any],
    params: PageParams,
    sort: list[tuple[str, int]],
    projection: dict[str, int] | None = None,
) -> tuple[list[dict[str, Any]], int]:
    """Run a paginated query; returns ``(documents, total_matching)``."""
    total = await collection.count_documents(query)
    cursor = collection.find(query, projection).sort(sort).skip(params.skip).limit(params.page_size)
    return await cursor.to_list(length=params.page_size), total
