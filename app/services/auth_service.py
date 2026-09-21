import logging
from typing import Any

from app.database.session import DuplicateKeyError

from app.core.config import Settings
from app.core.errors import ConflictError, NotFoundError, UnauthorizedError
from app.core.security import burn_password_check, create_access_token, hash_password, verify_password
from app.database.collections import C
from app.models.enums import ConsultationType, Gender, UserRole
from app.models.users import Doctor, Patient, User
from app.schemas.auth import RegisterRequest
from app.utils.object_id import oid

logger = logging.getLogger("nivara.auth")

INVALID_CREDENTIALS = "Invalid email or password"


class AuthService:
    def __init__(self, db: Any, settings: Settings) -> None:
        self.db = db
        self.settings = settings

    async def register(self, payload: RegisterRequest) -> dict:
        user = User(
            name=payload.name,
            email=payload.email,
            password_hash=hash_password(payload.password, self.settings.bcrypt_rounds),
            phone=payload.phone,
            role=payload.role,
        ).to_mongo()
        try:
            await self.db[C.USERS].insert_one(user)
        except DuplicateKeyError:
            raise ConflictError("An account with this email already exists", code="email_taken") from None

        try:
            if payload.role == UserRole.PATIENT:
                await self.db[C.PATIENTS].insert_one(
                    Patient(
                        user_id=user["_id"],
                        date_of_birth=payload.date_of_birth.isoformat() if payload.date_of_birth else None,
                        gender=payload.gender or Gender.UNDISCLOSED,
                    ).to_mongo()
                )
            else:
                types = [t.value for t in (payload.consultation_types or [ConsultationType.FIRST_VISIT, ConsultationType.FOLLOW_UP])]
                await self.db[C.DOCTORS].insert_one(
                    Doctor(
                        user_id=user["_id"],
                        name=payload.name,
                        specialty=payload.specialty or "",
                        experience=payload.experience,
                        consultation_fee=payload.consultation_fee,
                        consultation_types=types,
                    ).to_mongo()
                )
        except Exception:
            await self.db[C.USERS].delete_one({"_id": user["_id"]})  # don't leave a profile-less account
            raise
        return user

    async def authenticate(self, email: str, password: str) -> tuple[dict, str, int]:
        user = await self.db[C.USERS].find_one({"email": email.lower()})
        if user is None:
            burn_password_check(password, self.settings.bcrypt_rounds)  # equalise timing
            raise UnauthorizedError(INVALID_CREDENTIALS, code="invalid_credentials")
        if not verify_password(password, user["password_hash"]) or not user.get("is_active", False):
            raise UnauthorizedError(INVALID_CREDENTIALS, code="invalid_credentials")
        token, expires_in = create_access_token(user_id=str(user["_id"]), role=user["role"], settings=self.settings)
        return user, token, expires_in

    async def get_active_user(self, user_id: str) -> dict:
        user = await self.db[C.USERS].find_one({"_id": oid(user_id), "is_active": True})
        if user is None:
            raise UnauthorizedError("Invalid authentication token", code="invalid_token")
        return user

    async def get_user(self, user_id: str) -> dict:
        user = await self.db[C.USERS].find_one({"_id": oid(user_id)})
        if user is None:
            raise NotFoundError("User not found")
        return user
