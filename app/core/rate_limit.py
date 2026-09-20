"""Minimal in-process sliding-window rate limiter.

This is a *basic* protection for credential endpoints. State is per-process, so
with several workers/replicas the effective limit is multiplied — put a shared
limiter (API gateway, reverse proxy, or Redis-backed) in front for production.
"""
import time
from collections import defaultdict, deque

from fastapi import Request

from app.core.errors import TooManyRequestsError


class RateLimiter:
    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def check(self, key: str, limit: int, window_seconds: int = 60) -> None:
        now = time.monotonic()
        hits = self._hits[key]
        while hits and now - hits[0] > window_seconds:
            hits.popleft()
        if len(hits) >= limit:
            retry_after = max(1, int(window_seconds - (now - hits[0])))
            raise TooManyRequestsError(
                "Too many requests. Please try again later.",
                headers={"Retry-After": str(retry_after)},
            )
        hits.append(now)

    def reset(self) -> None:
        self._hits.clear()


def client_ip(request: Request) -> str:
    # NOTE: behind a proxy, configure uvicorn `--proxy-headers` / forwarded-allow-ips
    # so `request.client` reflects the real client rather than trusting raw headers.
    return request.client.host if request.client else "unknown"


async def auth_rate_limit(request: Request) -> None:
    settings = request.app.state.settings
    if not settings.rate_limit_enabled:
        return
    limiter: RateLimiter = request.app.state.rate_limiter
    limiter.check(f"auth:{client_ip(request)}:{request.url.path}", settings.rate_limit_auth_per_minute)
