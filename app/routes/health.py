from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter(tags=["Health"])


@router.get("/health", summary="Liveness check", description="Returns 200 if the process is up. **Auth:** none.")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/ready", summary="Readiness check (Database ping)",
            description="200 if database responds, 503 otherwise. **Auth:** none.")
async def ready(request: Request) -> Any:
    try:
        await request.app.state.db.command("ping")
    except Exception:  # noqa: BLE001
        return JSONResponse(status_code=503, content={"status": "unavailable", "database": "down"})
    return {"status": "ok", "database": "up"}
