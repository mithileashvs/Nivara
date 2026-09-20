"""Resolves which hospitals/departments are currently accepting new appointment requests."""
from typing import Any

from bson import ObjectId

from app.database.collections import C
from app.models.enums import DepartmentStatus, IntakeStatus


class IntakeService:
    def __init__(self, db: Any) -> None:
        self.db = db

    async def open_scope(
        self,
        *,
        hospital_ids: list[ObjectId] | None = None,
        department_ids: list[ObjectId] | None = None,
    ) -> tuple[list[ObjectId], list[ObjectId]]:
        """Return ``(open_hospital_ids, open_department_ids)``.

        A department is open only if it is ACTIVE with intake OPEN *and* its hospital is OPEN.
        Optional arguments restrict the lookup to a candidate set (keeps queries small).
        """
        hq: dict[str, Any] = {"appointment_intake_status": IntakeStatus.OPEN}
        if hospital_ids is not None:
            hq["_id"] = {"$in": hospital_ids}
        hospitals = await self.db[C.HOSPITALS].find(hq, {"_id": 1}).to_list(length=5000)
        open_hospitals = [h["_id"] for h in hospitals]
        if not open_hospitals:
            return [], []

        dq: dict[str, Any] = {
            "hospital_id": {"$in": open_hospitals},
            "status": DepartmentStatus.ACTIVE,
            "appointment_intake_status": IntakeStatus.OPEN,
        }
        if department_ids is not None:
            dq["_id"] = {"$in": department_ids}
        departments = await self.db[C.DEPARTMENTS].find(dq, {"_id": 1}).to_list(length=20000)
        return open_hospitals, [d["_id"] for d in departments]

    async def load_context(
        self, hospital_ids: set[ObjectId], department_ids: set[ObjectId]
    ) -> tuple[dict[ObjectId, dict], dict[ObjectId, dict]]:
        """Batch-load hospitals and departments keyed by id."""
        hospitals = {}
        departments = {}
        if hospital_ids:
            async for h in self.db[C.HOSPITALS].find({"_id": {"$in": list(hospital_ids)}}):
                hospitals[h["_id"]] = h
        if department_ids:
            async for d in self.db[C.DEPARTMENTS].find({"_id": {"$in": list(department_ids)}}):
                departments[d["_id"]] = d
        return hospitals, departments
