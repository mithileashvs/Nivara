# Nivara Backend

A FastAPI + Supabase PostgreSQL backend for healthcare appointment management: patients *request* appointments,
doctors accept or reject them, and admins manage platform resources — never individual appointments.

This README documents the **backend only**. The frontend React client is in `frontend/`.

---

## 1. Overview

Nivara lets patients find doctors, view real bookable slots, and request appointments. Doctors
manage their own working hours and decide on each request. Hospitals, departments and doctors can
each independently open/close new-appointment intake without touching appointments already in
progress. The backend also includes smart (but strictly non-medical) features: department routing
from symptoms, doctor matching, and appointment-slot optimisation.

**Medical safety, stated plainly:** Nivara does not diagnose medical conditions, does not
prescribe medicines, does not recommend medication or dosage, and does not generate treatment plans.
The "smart" features are appointment-discovery tools only.

## 2. Backend architecture

```
app/
  core/        settings, security (JWT/bcrypt), error handling, middleware, rate limiting
  database/    SQLAlchemy Core tables, PostgreSQL DDL schema, async DatabaseManager, TableRepository session abstraction
  models/      data models (pydantic, used for building/validating records and enums)
  schemas/     API request/response models (pydantic)
  services/    business logic — one service per domain, routes stay thin
  routes/      FastAPI routers — thin: parse request -> call service -> serialise response
  data/        static seed data for department-routing rules
scripts/       seed.py — development seed data
tests/         pytest suite running against PostgreSQL
```

Routes never talk to the database directly; they call a service, which owns its domain operations. Every
mutation that must be atomic (claiming a slot, transitioning an appointment) uses atomic, conditional SQL updates
with `RETURNING *` — the database itself is the source of truth for who "won" a race, not
application-level locks. See the appointment lifecycle in `app/services/appointment_service.py` for
the concurrency model in detail.

## 3. Technology stack

- **FastAPI** (async) on **Uvicorn**
- **PostgreSQL / Supabase** via **SQLAlchemy 2.0 (Core / async)** + **asyncpg** (with fallback support for **aiosqlite**)
- **Pydantic v2** for both settings and request/response validation
- **PyJWT** for stateless bearer-token auth, **bcrypt** for password hashing
- **Pytest** + **pytest-asyncio** + **httpx** for comprehensive automated testing

## 4. Requirements

- Python 3.12+
- PostgreSQL 16+ (local install, Supabase, or Docker)

## 5. Installation

```bash
git clone <this-repo>
cd Nivara
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt   # installs runtime + test dependencies
cp .env.example .env
# edit .env: set DATABASE_URL and JWT_SECRET at minimum (see below)
```

Generate a JWT secret:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

## 6. Environment variables

All variables are documented in `.env.example`. The important ones:

| Variable | Purpose |
|---|---|
| `ENVIRONMENT` | `development` / `test` / `production`. Production enforces a strong `JWT_SECRET` and disallows `CORS_ORIGINS=*`. |
| `DATABASE_URL`, `DATABASE_NAME` | PostgreSQL / Supabase connection URL. |
| `JWT_SECRET`, `JWT_ALGORITHM`, `ACCESS_TOKEN_EXPIRE_MINUTES` | Auth token signing. |
| `CORS_ORIGINS` | Comma-separated allowed browser origins. |
| `APP_TIMEZONE` | IANA timezone used to interpret slot dates/times (clinic-local wall clock). |
| `REQUEST_HOLD_MINUTES`, `MAX_PENDING_REQUESTS_PER_PATIENT`, `MAX_SCHEDULING_HORIZON_DAYS`, `MIN_BOOKING_LEAD_MINUTES` | Scheduling limits. |
| `BACKGROUND_JOBS_ENABLED`, `BACKGROUND_JOB_INTERVAL_SECONDS`, `REMINDER_HOURS_BEFORE` | Periodic housekeeping (expire stale holds, send reminders). |
| `WAITLIST_*` | Smart waitlist limits. |
| `RATE_LIMIT_*` | In-process rate limiting for auth endpoints. |

Never commit a real `.env` — `.gitignore` already excludes it.

## 7. Database setup

Any reachable PostgreSQL 16+ or Supabase instance works. For local development with Docker:

```bash
docker compose up -d postgres
```

Or connect directly to your Supabase project using the Transaction/Session pooling connection string:
`DATABASE_URL=postgresql+asyncpg://postgres:[YOUR-PASSWORD]@db.[YOUR-PROJECT-REF].supabase.co:5432/postgres`

The application creates all required tables and indexes automatically on startup via `app/database/tables.py` and `app/database/indexes.py`. Raw DDL is also provided in `app/database/schema.sql`.

## 8. Running FastAPI

```bash
uvicorn app.main:app --reload
```

The API is served under `/api/v1` (configurable via `API_PREFIX`). Swagger UI is at `/docs`, ReDoc
at `/redoc`, the raw OpenAPI schema at `/openapi.json`.

## 9. Running the seed script

To seed your Supabase PostgreSQL database with complete development data:

```bash
python scripts/seed_supabase.py
```

To verify the seed (tests authentication, profile status, and doctor search):

```bash
python scripts/verify_seed.py
```

Creates one admin, five doctors (across two hospitals / five departments), five patients, working
hours and slots for the next three days, and a handful of sample appointments in different lifecycle
states (confirmed, pending, rejected). It talks to the **same PostgreSQL database your app is configured to use**
(via `.env`) through the real API. It is idempotent — safe to run again; existing records are detected by email/name and skipped.

Credentials (all fictional, `@nivara.com`, never real personal data):

| Role | Email | Password |
|---|---|---|
| Admin | `admin@nivara.com` | `DevPass123!` |
| Doctor | `doctor1@nivara.com` … `doctor5@nivara.com` | `DevPass123!` |
| Patient | `patient1@nivara.com` … `patient5@nivara.com` | `DevPass123!` |

**Never reuse this password outside development.**

## 10. Running tests

```bash
pytest
```

Coverage includes: registration/login/JWT/deactivation, RBAC boundaries per role, doctor search and
availability, hospital/department CRUD and intake control, the full appointment lifecycle (request →
accept/reject → complete/no-show, cancel, reschedule), slot-conflict handling (409s), hospital /
department / doctor intake closure (new requests blocked, existing appointments untouched),
notification creation for every lifecycle event, admin platform management, the two statistics
endpoints, health checks, and deterministic concurrency tests (`tests/test_concurrency.py`).

## 11. Swagger documentation

Visit `/docs` once the server is running. Click **Authorize**, log in via `POST /api/v1/auth/token`
(the OAuth2-password-flow variant of login built specifically so the Swagger UI button works), and
all subsequent requests in the UI carry your bearer token.

## 12. Authentication

`POST /api/v1/auth/register` (patient/doctor only — admins cannot self-register) →
`POST /api/v1/auth/login` → JWT bearer token → `Authorization: Bearer <token>` on every subsequent
request. The current user's account is re-checked in the database on every request, so deactivating
a user revokes access immediately, not just at next-token-refresh.

## 13. Roles

- **PATIENT** — manages their own profile, requests/cancels/reschedules their own appointments.
- **DOCTOR** — manages their own profile, availability, and decides (accept/reject) on requests
  addressed to them; can complete/no-show/cancel/reschedule their own confirmed appointments.
- **ADMIN** — platform administrator. Two kinds, distinguished by `managed_hospital_ids`:
  - `None` → **platform-wide** admin (create hospitals, create other admins, verify doctors, etc.)
  - a list of hospital ids → **hospital administrator**, scoped to those hospitals only

Admins **never** accept/reject individual appointments — that decision belongs to the doctor alone.

## 14. Appointment lifecycle

```
Patient requests
      |
  REQUESTED  (slot atomically HELD; auto-expires after REQUEST_HOLD_MINUTES if the doctor doesn't respond)
      |
      +-- Doctor accepts --> CONFIRMED --+-- (after start time) --> COMPLETED
      |                                  |
      |                                  +-- (after start time) --> NO_SHOW
      |                                  |
      |                                  +-- cancel (by either party, before start) --> CANCELLED
      |
      +-- Doctor rejects --> REJECTED
      |
      +-- cancel (by either party, before start) --> CANCELLED
```

Every transition is a single conditional MongoDB update keyed on the appointment's *current* status,
so two racing decisions (e.g. accept + cancel at the same instant) can never both succeed — the loser
gets a `409 appointment_changed` (or a more specific code) and the winner's state is authoritative.

## 15. Slot management

Doctors publish **working windows** (`POST /doctors/me/availability`, `status=WORKING`), which
generate individual bookable slots at a fixed duration. **Time-off** windows (`status=BLOCKED`) block
overlapping *free* slots only — slots already held/booked by a patient are left untouched. A slot's
state machine is `AVAILABLE → HELD (patient requested) → BOOKED (doctor accepted)`, or back to
`AVAILABLE` on rejection/cancellation/expiry. Claiming a slot is one atomic conditional update — the
same mechanism that guarantees appointment conflict prevention.

## 16. Hospital intake control

Hospitals, departments, and doctors each have an independent `OPEN`/`CLOSED` intake flag:

- `PUT /hospitals/{id}/intake`
- `PUT /departments/{id}/intake`
- `PUT /doctors/{id}/intake-status`

Closing any of the three blocks **new** appointment requests at that level (`409` with a specific
error code such as `hospital_intake_closed`) but **never touches existing REQUESTED/CONFIRMED
appointments** — closing intake is a forward-looking control, not a cancellation tool. Available
capacity is always reported as real numbers computed from actual slot documents
(`GET /hospitals/{id}/availability` → `total_bookable_slots`, per-department `bookable_slots`) —
**never** as an invented "load" or "how full" percentage.

## 17. Smart department routing

`POST /smart/department-suggestion` maps a list of symptoms to a **department name**, for booking
purposes only. It returns `primary_department`, ranked `suggested_departments` with the rule that
matched, real bookable departments for that name, and a `disclaimer`. It ignores any input that reads
like a request for diagnosis, medication, dosage or treatment. This endpoint (and the related
`doctor-matching` / `appointment-options` endpoints) never influence what a doctor sees or does —
they only help a patient find a bookable slot faster.

## 18. Medical safety limitations

SmartCare, everywhere in this backend:

- **does not** diagnose medical conditions
- **does not** prescribe medicines
- **does not** recommend medication or dosage
- **does not** generate treatment plans

Every "smart" endpoint is explicitly appointment-discovery / routing only, and says so in its own
OpenAPI description.

## 19. API structure

All endpoints are versioned under `/api/v1` (see `app/core/config.py: api_prefix`). Every error
response has the same shape:

```json
{"error": {"code": "slot_unavailable", "message": "...", "details": null}, "request_id": "..."}
```

Main resource groups (see `/docs` for the full, current list — the OpenAPI schema is generated from
the code and is always authoritative):

| Prefix | Covers |
|---|---|
| `/auth` | register, login, token (OAuth2 form), me |
| `/patients` | own profile; admin listing |
| `/doctors` | search, own profile/availability, statistics, intake status |
| `/hospitals`, `/departments` | CRUD, intake control, availability report |
| `/slots` | search bookable slots; doctor's own full schedule; block/unblock |
| `/appointments` | request, list, get, history, accept/reject/cancel/complete/no-show/reschedule |
| `/notifications` | list, unread count, mark read |
| `/smart` | department-suggestion, doctor-matching, appointment-options |
| `/admin` | users, doctor verification/affiliation, routing rules, **statistics**, maintenance |
| `/health`, `/health/ready` | liveness / readiness |

(`/reviews`, `/medical-records`, `/waitlist` also exist — second-50%-phase features that were already
implemented before this milestone and were left untouched.)

## 20. Project structure

See section 2 above for the directory layout. Within each layer, one file per domain
(`hospital_service.py`, `appointment_service.py`, …) — routes stay thin and delegate all business
logic to the matching service.

---

## Running with Docker

```bash
docker compose up --build
docker compose exec backend python scripts/seed.py   # optional: seed development data
```

This starts MongoDB and the backend (with `--reload`) on `http://localhost:8000`. Set a real
`JWT_SECRET` via a `.env` file or the `JWT_SECRET` environment variable before using this beyond a
quick local try — the compose file falls back to an insecure default otherwise. The app runs
perfectly well **without** Docker too (section 5/8 above).

## New in this milestone

- `GET /api/v1/doctors/me/statistics` — today's appointments, pending requests, confirmed/completed
  counts, total distinct patients (DOCTOR only)
- `GET /api/v1/admin/statistics` — platform-wide user/hospital/department/doctor counts and
  appointment counts by status (platform ADMIN only)
- `scripts/seed.py`, this README, `Dockerfile` / `docker-compose.yml`
- Expanded Pytest coverage (see section 10)

Everything else listed in the "first 50%" milestone was already implemented and has been verified,
not rebuilt, as part of this work — see the audit notes in the project history for the full
before/after breakdown.
