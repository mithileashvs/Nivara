# Nivara

Healthcare appointment management platform built with **React, FastAPI, PostgreSQL, and Supabase**.

Nivara connects patients, doctors, and healthcare administrators through a role-based appointment workflow built around real slot availability, controlled intake, and transactional database operations.

## Overview

Patients can discover doctors, view available appointment slots, and request appointments. Doctors manage their availability and approve or reject appointment requests. Administrators manage hospitals, departments, doctors, users, and platform operations.

### Key capabilities

- Doctor discovery and search
- Real bookable appointment slots
- Patient appointment requests
- Doctor approval and rejection workflow
- Appointment cancellation and rescheduling
- Doctor availability management
- Hospital, department, and doctor intake controls
- Role-based access control
- Notifications and appointment history
- Smart department routing
- Doctor matching and appointment options
- Administrative statistics
- Automated testing
- OpenAPI / Swagger documentation

## Architecture

```text
React / Vite Frontend
        │
        ▼
FastAPI Backend
        │
        ▼
PostgreSQL / Supabase
```

The backend follows a layered structure:

```text
Routes
   ↓
Services
   ↓
Database
```

Routes remain thin and delegate domain operations to service modules. Database state is the source of truth for operations that require concurrency guarantees.

## Technology Stack

| Layer | Technology |
|---|---|
| Frontend | React, Vite, Tailwind CSS |
| Backend | FastAPI, Python |
| Database | PostgreSQL, Supabase |
| Database Access | SQLAlchemy 2.0, asyncpg |
| Validation | Pydantic v2 |
| Authentication | JWT, bcrypt |
| Testing | Pytest, pytest-asyncio, HTTPX |
| API Server | Uvicorn |
| Deployment | Vercel, Render |
| API Documentation | OpenAPI, Swagger UI |

## Roles

### Patient

- Manage personal profile
- Search and discover doctors
- View available slots
- Request appointments
- Cancel and reschedule appointments
- View appointment history
- Receive notifications

### Doctor

- Manage professional profile
- Manage working availability
- Review appointment requests
- Accept or reject appointment requests
- Manage confirmed appointments
- View appointment statistics

### Administrator

- Manage hospitals and departments
- Manage doctors and affiliations
- Manage users
- Control appointment intake
- View platform statistics
- Perform platform-level maintenance

Administrators do not approve individual appointment requests. Appointment decisions belong to the doctor associated with the request.

## Appointment Lifecycle

```text
Patient requests appointment
            │
            ▼
        REQUESTED
        /        \
       /          \
      ▼            ▼
 Doctor accepts   Doctor rejects
      │            │
      ▼            ▼
  CONFIRMED     REJECTED
      │
      ├──► COMPLETED
      ├──► NO_SHOW
      └──► CANCELLED
```

A requested appointment temporarily holds its slot. The hold expires automatically when the configured request window is exceeded without a doctor decision.

Appointment transitions use conditional database operations so concurrent requests cannot both successfully modify the same appointment state.

## Slot Management

Doctors publish working windows that generate individual bookable slots.

```text
AVAILABLE
    │
    ▼
  HELD
    │
    ▼
 BOOKED
```

Rejected, cancelled, or expired requests can release a held slot back to `AVAILABLE`.

Time-off and blocked availability affect free slots while preserving appointments that have already been requested or confirmed.

## Intake Control

Nivara supports independent intake control at three levels:

- Hospital
- Department
- Doctor

Closing intake prevents **new appointment requests** at that level. Existing appointments are not cancelled or modified.

Available capacity is calculated from actual bookable slots rather than an inferred hospital-load percentage.

## Smart Features

### Department Routing

Maps symptoms to a general department for appointment discovery. It does not diagnose a medical condition.

### Doctor Matching

Helps patients discover relevant doctors using available profile and scheduling information.

### Appointment Options

Helps patients identify bookable appointment choices.

These features are intended for appointment discovery and routing, not clinical decision-making.

## Medical Safety

Nivara's intelligent features are deliberately limited to appointment discovery and routing.

The system does **not**:

- Diagnose medical conditions
- Prescribe medicines
- Recommend medication or dosage
- Generate treatment plans

## Authentication & Security

- JWT bearer authentication
- bcrypt password hashing
- Role-based authorization
- Protected administrative operations
- Configurable CORS
- Rate limiting for authentication endpoints
- Environment-based configuration
- Production JWT secret enforcement
- User status checked against the database during authenticated requests

## API

All application endpoints are versioned under:

```text
/api/v1
```

Main resource groups:

```text
/auth
/patients
/doctors
/hospitals
/departments
/slots
/appointments
/notifications
/smart
/admin
/health
```

Once the backend is running:

```text
Swagger UI   → /docs
ReDoc        → /redoc
OpenAPI      → /openapi.json
```

## Project Structure

```text
Nivara/
├── app/
│   ├── core/
│   ├── database/
│   ├── models/
│   ├── schemas/
│   ├── services/
│   ├── routes/
│   └── data/
├── frontend/
├── tests/
├── scripts/
├── requirements.txt
├── requirements-dev.txt
├── Dockerfile
├── docker-compose.yml
└── README.md
```

## Local Development

### Backend

```bash
git clone <repository-url>
cd Nivara
python -m venv .venv
```

Windows:

```powershell
.venv\Scripts\activate
```

Linux / macOS:

```bash
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements-dev.txt
```

Create the environment file:

```bash
cp .env.example .env
```

Configure at minimum:

```text
DATABASE_URL
JWT_SECRET
```

Generate a JWT secret:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Start the backend:

```bash
uvicorn app.main:app --reload
```

The API runs on:

```text
http://localhost:8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

The frontend uses `VITE_API_BASE_URL` to locate the backend API.

## Database

Nivara uses PostgreSQL and supports Supabase as the hosted database layer.

For local development, PostgreSQL can be started with Docker:

```bash
docker compose up -d postgres
```

The application creates the required tables and indexes during startup. The database schema is also available in:

```text
app/database/schema.sql
```

## Development Seed Data

Development seed data can be created with:

```bash
python scripts/seed_supabase.py
```

To verify the seeded environment:

```bash
python scripts/verify_seed.py
```

The seed is intended for development and testing only.

Example development accounts:

| Role | Email | Password |
|---|---|---|
| Admin | `admin@nivara.com` | `DevPass123!` |
| Doctor | `doctor1@nivara.com` | `DevPass123!` |
| Doctor | `doctor2@nivara.com` | `DevPass123!` |
| Patient | `patient1@nivara.com` | `DevPass123!` |

**Do not reuse development credentials outside a development environment.**

## Testing

Run the complete test suite with:

```bash
pytest
```

Tests cover authentication, authorization, doctor discovery, availability, appointment lifecycle transitions, slot conflicts, intake controls, notifications, administration, health checks, and concurrency scenarios.

## Docker

Build and start the application with:

```bash
docker compose up --build
```

For production deployments, configure secrets and environment variables through the deployment platform rather than committing them to the repository.

## Deployment

The application can be deployed as separate frontend and backend services.

```text
Vercel
  │
  │ React frontend
  ▼
Render
  │
  │ FastAPI backend
  ▼
Supabase
  │
  │ PostgreSQL
  ▼
Database
```

Environment-specific configuration should be supplied through the deployment platform.

Never commit:

```text
.env
production credentials
database passwords
JWT secrets
API keys
```

## License

See the repository license file for licensing information.
