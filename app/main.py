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
from app.database.connection import DatabaseManager
from app.database.indexes import ensure_indexes
from app.routes import api_router
from app.routes.health import router as health_router
from app.services.department_routing_service import DepartmentRoutingService
from app.services.maintenance_service import MaintenanceService


logger = logging.getLogger("nivara")


DESCRIPTION = """
NIVARA — Intelligent Healthcare Appointment & Management System API.

**How it works.** Patients *request* appointments; the *doctor* accepts or rejects.
Admins manage platform resources and hospital intake but never approve individual appointments.

**Medical safety.** Nivara never diagnoses, prescribes, recommends medication or dosages,
or plans treatment. Symptom input is used only to suggest a *department* for booking.
Doctor matching is appointment discovery, not medical advice.

**Authenticate** with `POST /api/v1/auth/login`, then send
`Authorization: Bearer <token>`.

Errors always look like
`{"error": {"code", "message", "details"?}, "request_id"}`.
"""


TAGS = [
    {"name": "Auth", "description": "Registration, login and current user."},
    {"name": "Patients", "description": "Patient profiles."},
    {"name": "Doctors", "description": "Doctor search, profile and availability."},
    {
        "name": "Hospitals",
        "description": "Hospitals, intake control and slot-based availability.",
    },
    {
        "name": "Departments",
        "description": "Departments and department-level intake control.",
    },
    {
        "name": "Appointments",
        "description": "Request → doctor decision → completion lifecycle.",
    },
    {"name": "Slots", "description": "Bookable slots (computed by the backend)."},
    {
        "name": "Medical Records",
        "description": "Doctor-authored notes and document metadata.",
    },
    {"name": "Reviews", "description": "Reviews of completed appointments."},
    {"name": "Notifications", "description": "In-app notifications."},
    {
        "name": "Smart Waitlist",
        "description": "Get notified when a matching slot opens.",
    },
    {
        "name": "Smart Features",
        "description": "Department routing, doctor matching, appointment options.",
    },
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


def create_app(
    settings: Settings | None = None,
    db: Any | None = None,
) -> FastAPI:
    """
    Application factory.

    Pass `db` (for example, an in-memory driver) to skip
    the real PostgreSQL connection during tests.
    """

    settings = settings or get_settings()

    configure_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        manager: DatabaseManager | None = None

        # In normal development/production, connect to PostgreSQL/Supabase.
        if db is None:
            manager = DatabaseManager(settings)
            app.state.db = await manager.connect()

        # When tests provide a database instance, use that instead.
        await ensure_indexes(app.state.db)

        await DepartmentRoutingService(
            app.state.db
        ).ensure_default_rules()

        task = (
            asyncio.create_task(_background_loop(app))
            if settings.background_jobs_enabled
            else None
        )

        try:
            yield

        finally:
            if task:
                task.cancel()

            if manager:
                await manager.close()

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=DESCRIPTION,
        openapi_tags=TAGS,
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    app.state.settings = settings
    app.state.rate_limiter = RateLimiter()

    if db is not None:
        app.state.db = db

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=(
            bool(settings.cors_origins)
            and "*" not in settings.cors_origins
        ),
        allow_methods=[
            "GET",
            "POST",
            "PUT",
            "PATCH",
            "DELETE",
            "OPTIONS",
        ],
        allow_headers=[
            "Authorization",
            "Content-Type",
            "X-Request-ID",
        ],
        expose_headers=[
            "X-Request-ID",
            "Retry-After",
        ],
    )

    app.add_middleware(RequestContextMiddleware)

    register_exception_handlers(app)

    # Root health endpoint for infrastructure probes.
    app.include_router(health_router)

    # Versioned health endpoint.
    app.include_router(
        health_router,
        prefix=settings.api_prefix,
    )

    # Main Nivara API.
    app.include_router(
        api_router,
        prefix=settings.api_prefix,
    )

    return app


# IMPORTANT:
# Create the FastAPI application immediately.
#
# The previous implementation used:
#
#     app = None
#
# together with module __getattr__().
#
# `from app.main import app` retrieves the existing None value directly,
# so Uvicorn received None instead of a FastAPI application.
#
# Creating the application here makes:
#
#     uvicorn app.main:app
#
# work correctly.
app = create_app()