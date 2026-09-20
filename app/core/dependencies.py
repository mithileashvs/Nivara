"""Reusable FastAPI dependencies: DB/settings access, authentication, role-based authorization."""
from dataclasses import dataclass
from typing import Annotated, Any

from fastapi import Depends, Request
from fastapi.security import OAuth2PasswordBearer

from app.core.config import Settings
from app.core.errors import ForbiddenError, UnauthorizedError
from app.core.security import decode_access_token
from app.database.collections import C
from app.models.enums import UserRole
from app.services.appointment_service import Actor
from app.services.hospital_service import assert_can_manage_hospital  # noqa: F401  (re-exported)
from app.utils.object_id import oid

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token", auto_error=False)


def get_db(request: Request) -> Any:
    return request.app.state.db


def get_settings_dep(request: Request) -> Settings:
    return request.app.state.settings


DB = Annotated[Any, Depends(get_db)]
SettingsDep = Annotated[Settings, Depends(get_settings_dep)]


async def get_current_user(
    token: Annotated[str | None, Depends(oauth2_scheme)], db: DB, settings: SettingsDep
) -> dict:
    """Validate the bearer token AND re-check the account in the database on every request, so a
    deactivated user loses access immediately."""
    if not token:
        raise UnauthorizedError("Authentication required", code="not_authenticated")
    claims = decode_access_token(token, settings)
    try:
        user_id = oid(claims["sub"])
    except Exception:  # noqa: BLE001
        raise UnauthorizedError("Invalid authentication token", code="invalid_token") from None
    user = await db[C.USERS].find_one({"_id": user_id, "is_active": True})
    if user is None:
        raise UnauthorizedError("Invalid authentication token", code="invalid_token")
    return user


CurrentUser = Annotated[dict, Depends(get_current_user)]


def require_roles(*roles: UserRole):
    async def checker(user: CurrentUser) -> dict:
        if user["role"] not in roles:
            raise ForbiddenError("You do not have permission to perform this action", code="forbidden_role")
        return user

    return checker


@dataclass
class PatientContext:
    user: dict
    patient: dict

    @property
    def actor(self) -> Actor:
        return Actor(self.user["_id"], UserRole.PATIENT.value, self.patient["_id"], self.user["name"])


@dataclass
class DoctorContext:
    user: dict
    doctor: dict

    @property
    def actor(self) -> Actor:
        return Actor(self.user["_id"], UserRole.DOCTOR.value, self.doctor["_id"], self.user["name"])


async def require_patient(user: Annotated[dict, Depends(require_roles(UserRole.PATIENT))], db: DB) -> PatientContext:
    patient = await db[C.PATIENTS].find_one({"user_id": user["_id"]})
    if patient is None:
        raise ForbiddenError("Patient profile not found", code="profile_missing")
    return PatientContext(user, patient)


async def require_doctor(user: Annotated[dict, Depends(require_roles(UserRole.DOCTOR))], db: DB) -> DoctorContext:
    doctor = await db[C.DOCTORS].find_one({"user_id": user["_id"]})
    if doctor is None:
        raise ForbiddenError("Doctor profile not found", code="profile_missing")
    return DoctorContext(user, doctor)


require_admin = require_roles(UserRole.ADMIN)
AdminUser = Annotated[dict, Depends(require_admin)]
PatientCtx = Annotated[PatientContext, Depends(require_patient)]
DoctorCtx = Annotated[DoctorContext, Depends(require_doctor)]


async def require_participant(
    user: Annotated[dict, Depends(require_roles(UserRole.PATIENT, UserRole.DOCTOR))], db: DB
) -> Actor:
    """Patient or doctor acting on their own appointments. Admins are deliberately excluded."""
    if user["role"] == UserRole.PATIENT:
        profile = await db[C.PATIENTS].find_one({"user_id": user["_id"]})
    else:
        profile = await db[C.DOCTORS].find_one({"user_id": user["_id"]})
    if profile is None:
        raise ForbiddenError("Profile not found", code="profile_missing")
    return Actor(user["_id"], user["role"], profile["_id"], user["name"])


ParticipantActor = Annotated[Actor, Depends(require_participant)]
