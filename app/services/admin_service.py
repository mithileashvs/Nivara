from typing import Any

from pymongo.errors import DuplicateKeyError

from app.core.config import Settings
from app.core.errors import BadRequestError, ConflictError, ForbiddenError, NotFoundError
from app.core.security import hash_password
from app.database.collections import C
from app.models.enums import UserRole
from app.models.users import User
from app.schemas.admin import AdminUserCreate
from app.utils.object_id import oid, oids
from app.utils.pagination import PageParams, paginate
from app.utils.time_utils import utcnow


def require_platform_admin(user: dict) -> None:
    if user.get("managed_hospital_ids") is not None:
        raise ForbiddenError("This action requires a platform-wide administrator", code="platform_admin_required")


class AdminService:
    def __init__(self, db: Any, settings: Settings) -> None:
        self.db = db
        self.settings = settings

    async def _validate_hospitals(self, hospital_ids: list[str] | None):
        if hospital_ids is None:
            return None
        ids = oids(hospital_ids)
        if await self.db[C.HOSPITALS].count_documents({"_id": {"$in": ids}}) != len(set(ids)):
            raise BadRequestError("One or more hospitals do not exist", code="invalid_hospital")
        return list(dict.fromkeys(ids))

    async def create_admin(self, payload: AdminUserCreate) -> dict:
        user = User(
            name=payload.name, email=payload.email, phone=payload.phone, role=UserRole.ADMIN,
            password_hash=hash_password(payload.password, self.settings.bcrypt_rounds),
            managed_hospital_ids=await self._validate_hospitals(payload.managed_hospital_ids),
        ).to_mongo()
        try:
            await self.db[C.USERS].insert_one(user)
        except DuplicateKeyError:
            raise ConflictError("An account with this email already exists", code="email_taken") from None
        return user

    async def list_users(self, params: PageParams, role: UserRole | None, is_active: bool | None) -> tuple[list[dict], int]:
        query: dict[str, Any] = {}
        if role:
            query["role"] = role.value
        if is_active is not None:
            query["is_active"] = is_active
        return await paginate(self.db[C.USERS], query, params, sort=[("created_at", -1)])

    async def get_user(self, user_id: str) -> dict:
        user = await self.db[C.USERS].find_one({"_id": oid(user_id)})
        if user is None:
            raise NotFoundError("User not found", code="user_not_found")
        return user

    async def set_active(self, actor: dict, user_id: str, is_active: bool) -> dict:
        if actor["_id"] == oid(user_id):
            raise BadRequestError("You cannot change your own active status", code="cannot_modify_self")
        user = await self.get_user(user_id)
        return await self.db[C.USERS].find_one_and_update(
            {"_id": user["_id"]}, {"$set": {"is_active": is_active, "updated_at": utcnow()}}, return_document=True
        )

    async def set_scope(self, user_id: str, hospital_ids: list[str] | None) -> dict:
        user = await self.get_user(user_id)
        if user["role"] != UserRole.ADMIN:
            raise BadRequestError("Only admin users have a hospital scope", code="not_an_admin")
        scope = await self._validate_hospitals(hospital_ids)
        return await self.db[C.USERS].find_one_and_update(
            {"_id": user["_id"]}, {"$set": {"managed_hospital_ids": scope, "updated_at": utcnow()}}, return_document=True
        )

    # ------------------------------------------------------------------ statistics

    async def get_statistics(self) -> dict:
        """Basic platform counts. Every value is a live database count — never estimated or cached."""
        status_rows = await self.db[C.APPOINTMENTS].aggregate(
            [{"$group": {"_id": "$status", "n": {"$sum": 1}}}]
        ).to_list(length=None)
        by_status = {row["_id"]: row["n"] for row in status_rows}

        total_users = await self.db[C.USERS].count_documents({})
        total_patients = await self.db[C.PATIENTS].count_documents({})
        total_doctors = await self.db[C.DOCTORS].count_documents({})
        total_hospitals = await self.db[C.HOSPITALS].count_documents({})
        total_departments = await self.db[C.DEPARTMENTS].count_documents({})

        return {
            "total_users": total_users,
            "total_patients": total_patients,
            "total_doctors": total_doctors,
            "total_hospitals": total_hospitals,
            "total_departments": total_departments,
            "total_appointments": sum(by_status.values()),
            "requested_appointments": by_status.get("REQUESTED", 0),
            "confirmed_appointments": by_status.get("CONFIRMED", 0),
            "completed_appointments": by_status.get("COMPLETED", 0),
            "rejected_appointments": by_status.get("REJECTED", 0),
            "cancelled_appointments": by_status.get("CANCELLED", 0),
            "no_show_appointments": by_status.get("NO_SHOW", 0),
        }
