# Nivara — frontend

React + Vite + Tailwind client for the existing Nivara FastAPI backend.

The backend is the source of truth. Every screen here is wired to a real endpoint;
nothing is mocked, and no endpoint was invented. Where the backend does not support
something the design reference shows, the UI is adapted rather than faked — see
"Deliberate departures from the reference" below.

## Running it

Backend (from the backend repo):

```bash
pip install -r requirements-dev.txt
# .env must contain at least DATABASE_URL, JWT_SECRET and:
#   CORS_ORIGINS=http://localhost:5173
uvicorn app.main:app --reload            # http://localhost:8000
python -m scripts.seed                   # optional development data
```

Frontend:

```bash
cp .env.example .env                     # VITE_API_BASE_URL=http://localhost:8000
npm install
npm run dev                              # http://localhost:5173
```

`VITE_API_BASE_URL` is the backend origin **without** the `/api/v1` suffix — the
client adds it. It is read in exactly one place, `src/api/client.js`.

CORS: the backend only allows origins listed in its `CORS_ORIGINS`. If the app
loads but every request fails, that is almost always the cause.

## Architecture

```
src/
  api/          one module per backend tag; every call documented with its route + role
  components/   shared UI (domain) and components/ui (primitives)
  context/      AuthContext (JWT + session), ToastContext
  hooks/        useAsync, usePaged, useDirectory, useDebounced, useUnreadCount
  layouts/      DashboardLayout (sidebar shell), PublicLayout, AuthLayout
  pages/        public | patient | doctor | admin | hospital | shared
  routes/       AppRoutes + role guards
  utils/        constants (mirrors app/models/enums.py), errors, format, nav
```

## Authentication

`POST /auth/login` returns a JWT. It is held in module scope and mirrored into
`localStorage` (or `sessionStorage` when "remember me" is off). An Axios request
interceptor attaches `Authorization: Bearer <token>`; a response interceptor
clears the session on any 401 that is not a failed sign-in, and the user is
returned to `/login` with an explanation.

On boot, a stored token is re-validated against `GET /auth/me` rather than
trusted — so a revoked or expired token never yields a half-working session.

Route guards mirror the backend's rules so people are not shown screens whose
requests would be refused. **They do not replace backend authorisation**, which
is checked on every call and re-reads the account from the database each time.

## Roles

The backend has three roles: `PATIENT`, `DOCTOR`, `ADMIN`. A *hospital
administrator* is an `ADMIN` whose `managed_hospital_ids` is a list rather than
`null`. There is no separate hospital login, so none was created.

| Area        | Who                                            |
|-------------|------------------------------------------------|
| `/dashboard`| PATIENT                                        |
| `/doctor`   | DOCTOR                                         |
| `/admin`    | ADMIN with `managed_hospital_ids === null`     |
| `/hospital` | ADMIN with a `managed_hospital_ids` list       |

## Business rules the UI enforces

- A patient **requests**; the **doctor** accepts or declines. Administrators have
  no accept/reject/complete control anywhere in the UI, because the backend
  exposes none. `/admin/appointments` is strictly read-only.
- Closing intake (hospital, department or doctor) stops **new** requests only.
  Every intake dialog says so, and the success toast reports the backend's own
  `active_appointments_unaffected` count.
- Slot bookability is taken verbatim from the backend's computed `bookable`
  flag. The frontend never decides whether a time is available.
- Symptom input is routed to a **department**, never diagnosed. The disclaimer
  rendered is the backend's own `disclaimer` string where it returns one, and
  inputs the backend refuses are surfaced under "Some input was not used".
- No hospital "load" is shown. Availability figures are counts of genuinely open
  slots from `GET /hospitals/{id}/availability`.
- Ratings come from `rating_average` / `rating_count`; a doctor with no reviews
  shows "No reviews yet" rather than a fabricated score.

## Error handling

`src/api/client.js` normalises every failure to
`{ status, code, message, details, requestId }`. `src/utils/errors.js` maps the
backend's stable error `code` to patient-facing copy — for example
`slot_held` → "Another patient is already waiting on a decision for that slot."
Unmapped codes fall back to the backend's own message, which is always safe;
the backend never returns stack traces and none are ever rendered.

A 409 during booking returns the patient to slot selection with freshly reloaded
availability. 422 bodies are split into per-field messages via `fieldErrors`.

Every data-driven screen routes through `<AsyncBoundary>`, which covers loading,
error, empty and content in one place.

## Deliberate departures from the reference

| Reference shows | What was built | Why |
|---|---|---|
| Login tabs: Patient / Doctor / Admin / Hospital | Patient / Doctor / Admin | No hospital role exists; a note explains hospital admins sign in under Admin |
| Register tabs incl. Admin / Hospital | Patient / Doctor | `RegisterRequest` rejects `role=ADMIN`; admins are created by an admin |
| "Forgot password?" | Omitted | No password-reset endpoint |
| Google / Apple sign-in | Omitted | No OAuth on the backend |
| "In-person / Video consultation" | First visit / Follow-up / Routine check-up | The real `ConsultationType` values |
| Hospital dashboard "1,024 Patients" | Omitted for hospital admins | The patient-count endpoint is platform-admin only |
| Doctor bio paragraphs | Omitted | The backend stores no biography field |
| Document upload | "Link a document" | The backend stores metadata + an https URL; there is no upload endpoint |

## Backend endpoints used

76 of the backend's 80 routes are wired. The four unused are intentional:
`POST /auth/token` (Swagger's form-encoded variant of `/auth/login`),
`GET /health` and `GET /health/ready` (infrastructure probes), and
`GET /smart/doctor-matching` (the `POST` variant of the same service is used).

**No backend files were modified.**

## Accessibility & responsiveness

Semantic landmarks, a skip link, visible focus rings on every interactive
element, labelled inputs, `aria-live` on result counts and toasts, focus trapping
and restoration in modals, and `prefers-reduced-motion` respected.

Desktop gets the dark sidebar rail; below `lg` it becomes a drawer plus a
four-item bottom bar. Dense admin tables re-render as stacked cards on mobile via
`DataTable`, and wide content scrolls inside its own container so the page body
never scrolls sideways. Safe-area insets are handled for notched devices.
