import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import Settings, get_settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging
from app.core.middleware import RequestContextMiddleware
from app.core.rate_limit import RateLimiter
from app.database.connection import MongoManager
from app.database.indexes import ensure_indexes
from app.routes import api_router
from app.routes.health import router as health_router
from app.services.department_routing_service import DepartmentRoutingService
from app.services.maintenance_service import MaintenanceService

logger = logging.getLogger("smartcare")

DESCRIPTION = """
SmartCare backend API — healthcare appointment management.

**How it works.** Patients *request* appointments; the *doctor* accepts or rejects. Admins manage platform resources
and hospital intake but never approve individual appointments.

**Medical safety.** SmartCare never diagnoses, prescribes, recommends medication or dosages, or plans treatment.
Symptom input is used only to suggest a *department* for booking. Doctor matching is appointment discovery, not medical advice.

**Authenticate** with `POST /api/v1/auth/login`, then send `Authorization: Bearer <token>`.
Errors always look like `{"error": {"code", "message", "details"?}, "request_id"}`.
"""

TAGS = [
    {"name": "Auth", "description": "Registration, login and current user."},
    {"name": "Patients", "description": "Patient profiles."},
    {"name": "Doctors", "description": "Doctor search, profile and availability."},
    {"name": "Hospitals", "description": "Hospitals, intake control and slot-based availability."},
    {"name": "Departments", "description": "Departments and department-level intake control."},
    {"name": "Appointments", "description": "Request → doctor decision → completion lifecycle."},
    {"name": "Slots", "description": "Bookable slots (computed by the backend)."},
    {"name": "Medical Records", "description": "Doctor-authored notes and document metadata."},
    {"name": "Reviews", "description": "Reviews of completed appointments."},
    {"name": "Notifications", "description": "In-app notifications."},
    {"name": "Smart Waitlist", "description": "Get notified when a matching slot opens."},
    {"name": "Smart Features", "description": "Department routing, doctor matching, appointment options."},
    {"name": "Admin", "description": "Platform administration."},
    {"name": "Health", "description": "Liveness / readiness."},
]


async def _background_loop(app: FastAPI) -> None:
    settings: Settings = app.state.settings
    service = MaintenanceService(app.state.db, settings)
    while True:
        try:
            await asyncio.sleep(settings.background_job_interval_seconds)
            result = await service.run_all()
            if any(result.values()):
                logger.info("Maintenance: %s", result)
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001
            logger.exception("Maintenance loop error")


def create_app(settings: Settings | None = None, db: Any | None = None) -> FastAPI:
    """Application factory. Pass ``db`` (e.g. an in-memory driver) to skip the real MongoDB connection."""
    settings = settings or get_settings()
    configure_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        manager: MongoManager | None = None
        if db is None:
            manager = MongoManager(settings)
            app.state.db = await manager.connect()
        await ensure_indexes(app.state.db)
        await DepartmentRoutingService(app.state.db).ensure_default_rules()
        task = asyncio.create_task(_background_loop(app)) if settings.background_jobs_enabled else None
        try:
            yield
        finally:
            if task:
                task.cancel()
            if manager:
                await manager.close()

    app = FastAPI(
        title=settings.app_name, version=settings.app_version, description=DESCRIPTION, openapi_tags=TAGS, lifespan=lifespan,
        docs_url="/docs", redoc_url="/redoc", openapi_url="/openapi.json",
    )
    app.state.settings = settings
    app.state.rate_limiter = RateLimiter()
    if db is not None:
        app.state.db = db

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=bool(settings.cors_origins) and "*" not in settings.cors_origins,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
        expose_headers=["X-Request-ID", "Retry-After"],
    )
    app.add_middleware(RequestContextMiddleware)
    register_exception_handlers(app)
    # Unprefixed at root for infra probes (load balancers, Docker healthcheck) that expect a
    # fixed, unversioned path, AND mirrored under the versioned prefix per the documented API
    # structure ("All endpoints are versioned under /api/v1" — see README) and the test suite.
    app.include_router(health_router)
    app.include_router(health_router, prefix=settings.api_prefix)
    app.include_router(api_router, prefix=settings.api_prefix)
    return app


def _default_app() -> FastAPI:  # pragma: no cover - used by `uvicorn app.main:app`
    return create_app()


app = None  # populated lazily below so importing the module never requires a configured environment


def __getattr__(name: str) -> Any:
    global app
    if name == "app":
        if app is None:
            app = _default_app()
        return app
    raise AttributeError(name)
