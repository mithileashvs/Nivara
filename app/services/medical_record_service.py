"""Medical record service: consultation notes, secure documents, consent management, timeline, and access auditing.

Pure SQLAlchemy 2.0 Async + asyncpg implementation for Supabase PostgreSQL.
"""
from __future__ import annotations

import logging
import re
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    and_,
    asc,
    desc,
    func,
    insert,
    or_,
    select,
    update,
)
from sqlalchemy.exc import IntegrityError

from app.core.config import Settings
from app.core.errors import BadRequestError, ConflictError, ForbiddenError, NotFoundError
from app.database.collections import C
from app.database.session import _normalize_row
from app.database.tables import (
    TABLE_MAP,
    appointment_history_table,
    appointment_slots_table,
    appointments_table,
    doctor_availability_table,
    doctors_table,
    document_shares_table,
    medical_documents_table,
    medical_record_audits_table,
    medical_records_table,
    patients_table,
    users_table,
)
from app.models.enums import (
    AppointmentStatus,
    AuditAction,
    AuditEntityType,
    AuditSeverity,
    DocumentConsentStatus,
    MedicalAuditAction,
    MedicalDocumentCategory,
    NotificationType,
    UserRole,
)
from app.schemas.clinical import (
    DocumentCreate,
    MedicalRecordCreate,
)
from app.services.audit_service import AuditService
from app.services.notification_service import NotificationService
from app.services.storage_service import (
    MedicalStorageService,
    get_storage,
    sanitize_filename,
)
from app.utils.pagination import PageParams
from app.utils.time_utils import utcnow

logger = logging.getLogger("nivara.medical_records")

mdt = medical_documents_table
dst = document_shares_table
mat = medical_record_audits_table
mrt = medical_records_table
at = appointments_table
pt = patients_table
dt = doctors_table
ut = users_table

_HEX24_RE = re.compile(r"^[0-9a-fA-F]{24}$")


def _parse_uuid(value: Any, *, allow_hex_miss: bool = False) -> str | None:
    """Parse a UUID string for PostgreSQL Uuid columns.

    Raises BadRequestError (400) for malformed strings; optionally returns None for
    24-char hex legacy ObjectId strings so callers can safely return 404/empty.
    """
    if value is None:
        raise BadRequestError("Invalid identifier", code="invalid_id")
    s = str(value).strip()
    if not s:
        raise BadRequestError("Invalid identifier", code="invalid_id")
    try:
        return str(UUID(s))
    except (ValueError, AttributeError, TypeError):
        if allow_hex_miss and _HEX24_RE.fullmatch(s):
            return None
        raise BadRequestError("Invalid identifier", code="invalid_id") from None


class MedicalRecordService:
    def __init__(self, db: Any, settings: Settings) -> None:
        self.db = db
        self.settings = settings
        self.legacy_storage = get_storage(settings)
        self.storage = MedicalStorageService(settings)
        self.notifications = NotificationService(db)

    # ------------------------------------------------------------------ SQLAlchemy connection helpers

    @asynccontextmanager
    async def _get_conn(self, for_write: bool = False):
        if getattr(self.db, "_conn", None) is not None:
            yield self.db._conn
        else:
            async with self.db.connect() as conn:
                yield conn
                if for_write:
                    await conn.commit()

    async def _fetch_one(self, stmt: Any, table_name: str) -> dict[str, Any] | None:
        async with self._get_conn() as conn:
            res = await conn.execute(stmt)
            row = res.mappings().first()
            if row is None:
                return None
            return _normalize_row(dict(row), table_name)

    async def _fetch_all(self, stmt: Any, table_name: str) -> list[dict[str, Any]]:
        async with self._get_conn() as conn:
            res = await conn.execute(stmt)
            return [_normalize_row(dict(r), table_name) for r in res.mappings().all()]

    async def _count(self, stmt: Any) -> int:
        async with self._get_conn() as conn:
            res = await conn.execute(stmt)
            return res.scalar_one() or 0

    async def _execute_write(self, stmt: Any) -> int:
        async with self._get_conn(for_write=True) as conn:
            res = await conn.execute(stmt)
            return res.rowcount if res.rowcount is not None and res.rowcount >= 0 else 0

    async def _update_returning(self, stmt: Any, table_name: str) -> dict[str, Any] | None:
        async with self._get_conn(for_write=True) as conn:
            res = await conn.execute(stmt)
            row = res.mappings().first()
            if row is None:
                return None
            return _normalize_row(dict(row), table_name)

    # ------------------------------------------------------------------ Audit Trail

    async def record_audit(
        self,
        actor_id: str | None,
        actor_role: str,
        patient_id: str | None,
        action: MedicalAuditAction | str,
        document_id: str | None = None,
        reason: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Records an access or mutation event in medical_record_audits.
        Never stores actual document file content or clinical notes.
        """
        now = utcnow()
        act_val = action.value if hasattr(action, "value") else str(action)
        clean_meta = dict(metadata or {})
        # Guard against accidental secret/content leakage in audit metadata
        for forbidden in ("content", "file_bytes", "notes", "jwt", "token"):
            clean_meta.pop(forbidden, None)

        ins_stmt = insert(mat).values(
            id=str(uuid4()),
            actor_id=str(actor_id) if actor_id else None,
            actor_role=str(actor_role),
            patient_id=str(patient_id) if patient_id else None,
            document_id=str(document_id) if document_id else None,
            action=act_val,
            reason=reason,
            metadata=clean_meta,
            created_at=now,
        )
        try:
            await self._execute_write(ins_stmt)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to record medical record audit: %s", exc)

        # Complementary centralized metadata-only audit entry (strictly zero clinical notes/filenames/titles).
        action_map = {
            MedicalAuditAction.UPLOAD.value: AuditAction.MEDICAL_DOCUMENT_UPLOADED,
            MedicalAuditAction.VIEW.value: AuditAction.MEDICAL_DOCUMENT_VIEWED,
            MedicalAuditAction.DOWNLOAD.value: AuditAction.MEDICAL_DOCUMENT_DOWNLOADED,
            MedicalAuditAction.DELETE.value: AuditAction.MEDICAL_DOCUMENT_DELETED,
            MedicalAuditAction.SHARE_GRANTED.value: AuditAction.MEDICAL_DOCUMENT_SHARED,
            MedicalAuditAction.SHARE_REVOKED.value: AuditAction.MEDICAL_DOCUMENT_REVOKED,
            MedicalAuditAction.UNAUTHORIZED_ATTEMPT.value: AuditAction.MEDICAL_DOCUMENT_UNAUTHORIZED_ATTEMPT,
        }
        mapped_action = action_map.get(act_val)
        if mapped_action is not None:
            is_unauth = act_val == MedicalAuditAction.UNAUTHORIZED_ATTEMPT.value
            is_dl = act_val == MedicalAuditAction.DOWNLOAD.value
            safe_central_meta = {
                "audit_source": "medical_record_audits",
                "medical_action": act_val,
                "document_id": str(document_id) if document_id else None,
                "patient_id": str(patient_id) if patient_id else None,
                "category": clean_meta.get("category"),
            }
            desc = (
                "Unauthorized medical document access attempt blocked"
                if is_unauth
                else f"Medical document event ({act_val}) recorded (clinical contents restricted)"
            )
            await AuditService(self.db, self.settings).log_event(
                action=mapped_action,
                entity_type=AuditEntityType.MEDICAL_DOCUMENT,
                entity_id=str(document_id) if document_id else None,
                actor_id=str(actor_id) if actor_id else None,
                actor_role=str(actor_role),
                hospital_id=None,
                severity=AuditSeverity.WARNING if is_unauth else AuditSeverity.INFO,
                description=desc,
                metadata=safe_central_meta,
                check_security_thresholds=(is_unauth or is_dl),
            )

    # ------------------------------------------------------------------ Doctor Consultation Notes (Preserved)

    async def create(self, doctor_id: Any, payload: MedicalRecordCreate) -> dict:
        """The treating doctor records consultation notes for an appointment."""
        now = utcnow()
        d_id = str(doctor_id)
        appt_uuid = _parse_uuid(payload.appointment_id, allow_hex_miss=True)
        if appt_uuid is None:
            raise NotFoundError("Appointment not found", code="appointment_not_found")
        appt_stmt = select(at).where(and_(at.c.id == appt_uuid, at.c.doctor_id == d_id))
        appt = await self._fetch_one(appt_stmt, C.APPOINTMENTS)
        if appt is None:
            raise NotFoundError("Appointment not found", code="appointment_not_found")
        if appt["status"] not in (AppointmentStatus.CONFIRMED.value, AppointmentStatus.COMPLETED.value):
            raise ConflictError("Notes can only be added to confirmed or completed appointments", code="invalid_appointment_status")

        rec_id = str(uuid4())
        ins_stmt = insert(mrt).values(
            id=rec_id,
            patient_id=appt["patient_id"],
            doctor_id=d_id,
            appointment_id=appt["_id"],
            notes=payload.notes,
            documents=[],
            created_at=now,
            updated_at=now,
        )
        try:
            await self._execute_write(ins_stmt)
        except IntegrityError:
            raise ConflictError("A medical record already exists for this appointment", code="record_exists") from None

        return await self._fetch_one(select(mrt).where(mrt.c.id == rec_id), C.MEDICAL_RECORDS)

    def _notes_scope(self, role: str, profile_id: Any) -> list[Any]:
        if role == UserRole.PATIENT.value:
            return [mrt.c.patient_id == str(profile_id)]
        if role == UserRole.DOCTOR.value:
            return [mrt.c.doctor_id == str(profile_id)]
        raise ForbiddenError("Administrators cannot access medical records", code="forbidden_role")

    async def get(self, role: str, profile_id: Any, record_id: str) -> dict:
        rec_uuid = _parse_uuid(record_id, allow_hex_miss=True)
        if rec_uuid is None:
            raise NotFoundError("Medical record not found", code="record_not_found")
        clauses = [mrt.c.id == rec_uuid, *self._notes_scope(role, profile_id)]
        doc = await self._fetch_one(select(mrt).where(and_(*clauses)), C.MEDICAL_RECORDS)
        if doc is None:
            raise NotFoundError("Medical record not found", code="record_not_found")
        return doc

    async def list(
        self,
        role: str,
        profile_id: Any,
        params: PageParams,
        *,
        patient_id: str | None,
        appointment_id: str | None,
    ) -> tuple[list[dict], int]:
        clauses = list(self._notes_scope(role, profile_id))
        if patient_id and role == UserRole.DOCTOR.value:
            p_uuid = _parse_uuid(patient_id, allow_hex_miss=True)
            if p_uuid is None:
                return [], 0
            clauses.append(mrt.c.patient_id == p_uuid)
        if appointment_id:
            a_uuid = _parse_uuid(appointment_id, allow_hex_miss=True)
            if a_uuid is None:
                return [], 0
            clauses.append(mrt.c.appointment_id == a_uuid)

        where_cond = and_(*clauses)
        total = await self._count(select(func.count()).select_from(mrt).where(where_cond))
        stmt = (
            select(mrt)
            .where(where_cond)
            .order_by(desc(mrt.c.created_at))
            .offset(params.offset)
            .limit(params.page_size)
        )
        items = await self._fetch_all(stmt, C.MEDICAL_RECORDS)
        return items, total

    async def update_notes(self, doctor_id: Any, record_id: str, notes: str) -> dict:
        rec_uuid = _parse_uuid(record_id, allow_hex_miss=True)
        if rec_uuid is None:
            raise NotFoundError("Medical record not found", code="record_not_found")
        now = utcnow()
        stmt = (
            update(mrt)
            .where(and_(mrt.c.id == rec_uuid, mrt.c.doctor_id == str(doctor_id)))
            .values(notes=notes, updated_at=now)
            .returning(mrt)
        )
        doc = await self._update_returning(stmt, C.MEDICAL_RECORDS)
        if doc is None:
            raise NotFoundError("Medical record not found", code="record_not_found")
        return doc

    async def add_document(self, role: str, profile_id: Any, user_id: Any, record_id: str, payload: DocumentCreate) -> dict:
        record = await self.get(role, profile_id, record_id)
        now = utcnow()
        meta = {
            "id": str(uuid4()),
            "filename": payload.filename,
            "file_url": self.legacy_storage.validate_reference(str(payload.file_url)),
            "document_type": payload.document_type.value,
            "uploaded_by": str(user_id),
            "uploader_role": role,
            "uploaded_at": now.isoformat(),
        }
        docs = list(record.get("documents") or []) + [meta]
        stmt = (
            update(mrt)
            .where(mrt.c.id == record["_id"])
            .values(documents=docs, updated_at=now)
            .returning(mrt)
        )
        return await self._update_returning(stmt, C.MEDICAL_RECORDS)

    async def remove_document(self, user_id: Any, role: str, profile_id: Any, record_id: str, document_id: str) -> dict:
        record = await self.get(role, profile_id, record_id)
        docs = list(record.get("documents") or [])
        target_doc = next((d for d in docs if str(d.get("id")) == str(document_id) and str(d.get("uploaded_by")) == str(user_id)), None)
        if target_doc is None:
            raise NotFoundError("Document not found or not uploaded by you", code="document_not_found")
        remaining = [d for d in docs if str(d.get("id")) != str(document_id)]
        now = utcnow()
        stmt = (
            update(mrt)
            .where(mrt.c.id == record["_id"])
            .values(documents=remaining, updated_at=now)
            .returning(mrt)
        )
        return await self._update_returning(stmt, C.MEDICAL_RECORDS)

    # ------------------------------------------------------------------ Phase 4: Secure Medical Documents (Patient-Owned)

    async def upload_document(
        self,
        patient: dict,
        title: str,
        category: str,
        description: str | None,
        appointment_id: str | None,
        filename: str,
        content: bytes,
        client_ip: str | None = None,
    ) -> dict:
        """Securely validates, stores, and registers a patient's medical document."""
        now = utcnow()
        patient_id = patient["_id"]
        user_id = patient["user_id"]

        # Validate category
        valid_cats = {c.value for c in MedicalDocumentCategory}
        if category not in valid_cats:
            category = MedicalDocumentCategory.OTHER.value

        # Validate optional appointment association
        valid_appt_id = None
        if appointment_id:
            appt_uuid = _parse_uuid(appointment_id, allow_hex_miss=True)
            if appt_uuid is not None:
                appt = await self._fetch_one(
                    select(at.c.id).where(and_(at.c.id == appt_uuid, at.c.patient_id == patient_id)),
                    C.APPOINTMENTS,
                )
                if appt:
                    valid_appt_id = str(appt["id"])

        clean_name = sanitize_filename(filename)
        storage_path, verified_mime, file_size, provider = await self.storage.save_file(
            patient_id=patient_id,
            original_filename=clean_name,
            content=content,
        )

        doc_id = str(uuid4())
        ins_stmt = insert(mdt).values(
            id=doc_id,
            patient_id=patient_id,
            patient_user_id=user_id,
            title=title.strip() or clean_name,
            category=category,
            description=description.strip() if description else None,
            filename=clean_name,
            file_type=verified_mime,
            file_size=file_size,
            storage_path=storage_path,
            storage_provider=provider,
            appointment_id=valid_appt_id,
            is_deleted=False,
            deleted_at=None,
            created_at=now,
            updated_at=now,
        )
        await self._execute_write(ins_stmt)

        # Audit upload
        await self.record_audit(
            actor_id=user_id,
            actor_role=UserRole.PATIENT.value,
            patient_id=patient_id,
            action=MedicalAuditAction.UPLOAD,
            document_id=doc_id,
            metadata={"filename": clean_name, "file_type": verified_mime, "size": file_size, "category": category, "ip": client_ip},
        )

        logger.info("Registered medical document %s for patient %s", doc_id, patient_id)
        doc = await self.get_patient_document(patient_id, doc_id)
        return doc

    async def list_patient_documents(
        self,
        patient_id: str,
        category: str | None = None,
        search: str | None = None,
        params: PageParams | None = None,
    ) -> tuple[list[dict], int]:
        """Lists active documents for a patient with filtering and active share metadata."""
        clauses = [mdt.c.patient_id == str(patient_id), mdt.c.is_deleted.is_(False)]
        if category:
            clauses.append(mdt.c.category == category)
        if search and search.strip():
            term = f"%{search.strip().lower()}%"
            clauses.append(or_(func.lower(mdt.c.title).like(term), func.lower(mdt.c.description).like(term)))

        where_cond = and_(*clauses)
        total = await self._count(select(func.count()).select_from(mdt).where(where_cond))

        query = select(mdt).where(where_cond).order_by(desc(mdt.c.created_at))
        if params:
            query = query.offset(params.offset).limit(params.page_size)

        docs = await self._fetch_all(query, C.MEDICAL_DOCUMENTS)

        # Enrich each document with its active shares
        enriched: list[dict] = []
        for d in docs:
            shares = await self.list_document_shares(patient_id, d["_id"])
            d["shares"] = shares
            enriched.append(d)

        return enriched, total

    async def get_patient_document(self, patient_id: str, document_id: str) -> dict:
        doc_uuid = _parse_uuid(document_id, allow_hex_miss=True)
        if doc_uuid is None:
            raise NotFoundError("Medical document not found", code="document_not_found")
        stmt = select(mdt).where(
            and_(mdt.c.id == doc_uuid, mdt.c.patient_id == str(patient_id), mdt.c.is_deleted.is_(False))
        )
        doc = await self._fetch_one(stmt, C.MEDICAL_DOCUMENTS)
        if doc is None:
            raise NotFoundError("Medical document not found", code="document_not_found")
        doc["shares"] = await self.list_document_shares(patient_id, doc_uuid)
        return doc

    async def delete_patient_document(self, patient_id: str, user_id: str, document_id: str, client_ip: str | None = None) -> dict:
        """Soft-deletes a document, revokes active shares, and purges the stored file."""
        doc = await self.get_patient_document(patient_id, document_id)
        doc_uuid = doc["_id"]
        now = utcnow()

        # 1. Mark document deleted
        upd_stmt = (
            update(mdt)
            .where(and_(mdt.c.id == doc_uuid, mdt.c.patient_id == str(patient_id)))
            .values(is_deleted=True, deleted_at=now, updated_at=now)
            .returning(mdt)
        )
        updated = await self._update_returning(upd_stmt, C.MEDICAL_DOCUMENTS)

        # 2. Revoke all active shares
        revoke_stmt = (
            update(dst)
            .where(and_(dst.c.document_id == doc_uuid, dst.c.consent_status == DocumentConsentStatus.GRANTED.value))
            .values(consent_status=DocumentConsentStatus.REVOKED.value, revoked_at=now, updated_at=now)
        )
        await self._execute_write(revoke_stmt)

        # 3. Purge physical file safely
        try:
            await self.storage.delete_file(doc["storage_path"], doc.get("storage_provider", "LOCAL"))
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to delete physical file %s from storage: %s", doc["storage_path"], exc)

        # 4. Audit deletion
        await self.record_audit(
            actor_id=user_id,
            actor_role=UserRole.PATIENT.value,
            patient_id=patient_id,
            action=MedicalAuditAction.DELETE,
            document_id=doc_uuid,
            metadata={"title": doc["title"], "ip": client_ip},
        )

        return updated or doc

    # ------------------------------------------------------------------ Secure Download & Authorization

    async def download_document(
        self,
        user: dict,
        document_id: str,
        client_ip: str | None = None,
    ) -> tuple[bytes, str, str]:
        """Validates ownership or active consent, then streams the private file.

        Returns:
            (file_bytes, file_type, original_filename)
        Raises:
            NotFoundError if document does not exist.
            ForbiddenError if user is not authorized, logging an UNAUTHORIZED_ATTEMPT.
        """
        doc_uuid = _parse_uuid(document_id, allow_hex_miss=True)
        if doc_uuid is None:
            raise NotFoundError("Medical document not found", code="document_not_found")
        stmt = select(mdt).where(and_(mdt.c.id == doc_uuid, mdt.c.is_deleted.is_(False)))
        doc = await self._fetch_one(stmt, C.MEDICAL_DOCUMENTS)
        if not doc:
            raise NotFoundError("Medical document not found", code="document_not_found")

        patient_id = doc["patient_id"]
        user_role = user["role"]
        user_id = user["_id"]

        is_authorized = False

        # 1. Patient check: owns the document
        if user_role == UserRole.PATIENT.value:
            patient = await self._fetch_one(select(pt.c.id).where(pt.c.user_id == user_id), C.PATIENTS)
            if patient and str(patient["id"]) == str(patient_id):
                is_authorized = True

        # 2. Doctor check: explicit active consent granted
        elif user_role == UserRole.DOCTOR.value:
            doctor = await self._fetch_one(select(dt.c.id).where(dt.c.user_id == user_id), C.DOCTORS)
            if doctor:
                doctor_id = str(doctor["id"])
                share = await self._fetch_one(
                    select(dst).where(
                        and_(
                            dst.c.document_id == doc_uuid,
                            dst.c.doctor_id == doctor_id,
                            dst.c.consent_status == DocumentConsentStatus.GRANTED.value,
                        )
                    ),
                    C.DOCUMENT_SHARES,
                )
                if share:
                    is_authorized = True

        # 3. Admins have NO clinical document access
        if not is_authorized:
            await self.record_audit(
                actor_id=user_id,
                actor_role=user_role,
                patient_id=patient_id,
                action=MedicalAuditAction.UNAUTHORIZED_ATTEMPT,
                document_id=doc_uuid,
                reason="Attempted unauthorized download/view of private medical document",
                metadata={"ip": client_ip, "role": user_role},
            )
            raise ForbiddenError("You are not authorized to access or download this document", code="access_denied")

        # Load file bytes
        data, _ = await self.storage.read_file_bytes(doc["storage_path"], doc.get("storage_provider", "LOCAL"))

        # Audit successful download
        await self.record_audit(
            actor_id=user_id,
            actor_role=user_role,
            patient_id=patient_id,
            action=MedicalAuditAction.DOWNLOAD,
            document_id=doc_uuid,
            metadata={"ip": client_ip, "title": doc["title"]},
        )

        return data, doc["file_type"], doc["filename"]

    # ------------------------------------------------------------------ Patient-Controlled Sharing & Consent

    async def share_document_with_doctor(
        self,
        patient: dict,
        document_id: str,
        doctor_id: str,
        appointment_id: str | None = None,
        notes: str | None = None,
        client_ip: str | None = None,
    ) -> dict:
        """Patient grants explicit consent for a verified doctor to view a document."""
        now = utcnow()
        patient_id = patient["_id"]
        doc = await self.get_patient_document(patient_id, document_id)
        doc_uuid = doc["_id"]

        # Enforce patient_id consistency between medical_documents and document_shares
        if str(doc["patient_id"]) != str(patient_id):
            raise ForbiddenError("Document ownership mismatch", code="forbidden_document")

        doctor_uuid = _parse_uuid(doctor_id, allow_hex_miss=True)
        if doctor_uuid is None:
            raise NotFoundError("Doctor not found or inactive", code="doctor_not_found")

        # Verify doctor exists and is active
        doc_stmt = select(dt).where(and_(dt.c.id == doctor_uuid, dt.c.profile_status == "ACTIVE"))
        doctor = await self._fetch_one(doc_stmt, C.DOCTORS)
        if not doctor:
            raise NotFoundError("Doctor not found or inactive", code="doctor_not_found")

        # Validate optional appointment_id belongs to patient
        valid_appt_id = None
        if appointment_id:
            appt_uuid = _parse_uuid(appointment_id, allow_hex_miss=True)
            if appt_uuid is not None:
                appt = await self._fetch_one(
                    select(at.c.id).where(and_(at.c.id == appt_uuid, at.c.patient_id == patient_id)),
                    C.APPOINTMENTS,
                )
                if appt:
                    valid_appt_id = str(appt["id"])

        # Check for currently active share (protected by uq_document_shares_active partial unique index)
        active_share = await self._fetch_one(
            select(dst).where(
                and_(
                    dst.c.document_id == doc_uuid,
                    dst.c.doctor_id == doctor_uuid,
                    dst.c.consent_status == DocumentConsentStatus.GRANTED.value,
                )
            ),
            C.DOCUMENT_SHARES,
        )

        if active_share:
            # Active consent already exists: update notes/appointment metadata if provided
            if valid_appt_id or notes is not None:
                upd_stmt = (
                    update(dst)
                    .where(dst.c.id == active_share["_id"])
                    .values(
                        appointment_id=valid_appt_id or active_share.get("appointment_id"),
                        notes=notes if notes is not None else active_share.get("notes"),
                        updated_at=now,
                    )
                    .returning(dst)
                )
                share_record = await self._update_returning(upd_stmt, C.DOCUMENT_SHARES)
            else:
                share_record = active_share
        else:
            # Insert a new share record so previous REVOKED shares remain preserved for history
            share_id = str(uuid4())
            ins_stmt = insert(dst).values(
                id=share_id,
                document_id=doc_uuid,
                patient_id=patient_id,
                doctor_id=doctor_uuid,
                appointment_id=valid_appt_id,
                consent_status=DocumentConsentStatus.GRANTED.value,
                granted_at=now,
                revoked_at=None,
                notes=notes,
                created_at=now,
                updated_at=now,
            )
            await self._execute_write(ins_stmt)
            share_record = await self._fetch_one(select(dst).where(dst.c.id == share_id), C.DOCUMENT_SHARES)

        # Audit sharing
        await self.record_audit(
            actor_id=patient["user_id"],
            actor_role=UserRole.PATIENT.value,
            patient_id=patient_id,
            action=MedicalAuditAction.SHARE_GRANTED,
            document_id=doc_uuid,
            metadata={"doctor_id": doctor_uuid, "doctor_name": doctor["name"], "ip": client_ip},
        )

        patient_user = await self._fetch_one(select(ut.c.name).where(ut.c.id == patient["user_id"]), C.USERS)
        patient_name = patient_user.get("name") if patient_user else patient.get("name") or "A patient"

        # Notify doctor
        await self.notifications.notify(
            user_id=doctor["user_id"],
            type=NotificationType.SYSTEM_ANNOUNCEMENT.value,
            title="Medical document shared",
            message=f"{patient_name} shared a medical document with you: '{doc['title']}'.",
            category="SYSTEM",
            action_url="/doctor/patients",
            data={"document_id": doc_uuid, "patient_id": patient_id},
        )

        return {**share_record, "doctor_name": doctor["name"], "doctor_specialty": doctor.get("specialty")}

    async def revoke_document_share(
        self,
        patient: dict,
        document_id: str,
        doctor_id: str,
        client_ip: str | None = None,
    ) -> dict:
        """Patient immediately revokes a doctor's consent to access a document."""
        now = utcnow()
        patient_id = patient["_id"]
        doc = await self.get_patient_document(patient_id, document_id)
        doc_uuid = doc["_id"]
        doctor_uuid = _parse_uuid(doctor_id, allow_hex_miss=True)
        if doctor_uuid is None:
            raise NotFoundError("Active share authorization not found", code="share_not_found")

        upd_stmt = (
            update(dst)
            .where(
                and_(
                    dst.c.document_id == doc_uuid,
                    dst.c.patient_id == str(patient_id),
                    dst.c.doctor_id == doctor_uuid,
                    dst.c.consent_status == DocumentConsentStatus.GRANTED.value,
                )
            )
            .values(
                consent_status=DocumentConsentStatus.REVOKED.value,
                revoked_at=now,
                updated_at=now,
            )
            .returning(dst)
        )
        revoked = await self._update_returning(upd_stmt, C.DOCUMENT_SHARES)
        if not revoked:
            raise NotFoundError("Active share authorization not found", code="share_not_found")

        await self.record_audit(
            actor_id=patient["user_id"],
            actor_role=UserRole.PATIENT.value,
            patient_id=patient_id,
            action=MedicalAuditAction.SHARE_REVOKED,
            document_id=doc_uuid,
            metadata={"doctor_id": doctor_uuid, "ip": client_ip},
        )
        return revoked

    async def list_document_shares(self, patient_id: str, document_id: str) -> list[dict]:
        """Lists active and historical sharing consents for a patient's document."""
        doc_uuid = _parse_uuid(document_id, allow_hex_miss=True)
        if doc_uuid is None:
            return []
        stmt = (
            select(
                dst,
                dt.c.name.label("doctor_name"),
                dt.c.specialty.label("doctor_specialty"),
            )
            .select_from(dst.join(dt, dst.c.doctor_id == dt.c.id, isouter=True))
            .where(and_(dst.c.document_id == doc_uuid, dst.c.patient_id == str(patient_id)))
            .order_by(desc(dst.c.granted_at))
        )
        return await self._fetch_all(stmt, C.DOCUMENT_SHARES)

    # ------------------------------------------------------------------ Doctor Shared Access

    async def list_shared_with_doctor(
        self,
        doctor_id: str,
        category: str | None = None,
        patient_id: str | None = None,
        params: PageParams | None = None,
    ) -> tuple[list[dict], int]:
        """Lists documents shared with the authenticated doctor under active consent."""
        clauses = [
            dst.c.doctor_id == str(doctor_id),
            dst.c.consent_status == DocumentConsentStatus.GRANTED.value,
            mdt.c.is_deleted.is_(False),
        ]
        if category:
            clauses.append(mdt.c.category == category)
        if patient_id:
            p_uuid = _parse_uuid(patient_id, allow_hex_miss=True)
            if p_uuid is None:
                return [], 0
            clauses.append(mdt.c.patient_id == p_uuid)

        from_clause = (
            dst.join(mdt, dst.c.document_id == mdt.c.id)
            .join(pt, mdt.c.patient_id == pt.c.id)
            .join(ut, pt.c.user_id == ut.c.id, isouter=True)
        )
        where_cond = and_(*clauses)

        total_stmt = select(func.count()).select_from(from_clause).where(where_cond)
        total = await self._count(total_stmt)

        stmt = (
            select(
                mdt,
                ut.c.name.label("patient_name"),
                dst.c.granted_at.label("shared_at"),
                dst.c.notes.label("share_notes"),
            )
            .select_from(from_clause)
            .where(where_cond)
            .order_by(desc(dst.c.granted_at))
        )
        if params:
            stmt = stmt.offset(params.offset).limit(params.page_size)

        items = await self._fetch_all(stmt, C.MEDICAL_DOCUMENTS)
        return items, total

    async def get_shared_document_for_doctor(self, doctor: dict, document_id: str, client_ip: str | None = None) -> dict:
        """Inspects shared document metadata as an authorized doctor."""
        doctor_id = doctor["_id"]
        doc_uuid = _parse_uuid(document_id, allow_hex_miss=True)
        if doc_uuid is None:
            raise ForbiddenError("You do not have active consent to access this document", code="access_denied")
        share = await self._fetch_one(
            select(dst).where(
                and_(
                    dst.c.document_id == doc_uuid,
                    dst.c.doctor_id == str(doctor_id),
                    dst.c.consent_status == DocumentConsentStatus.GRANTED.value,
                )
            ),
            C.DOCUMENT_SHARES,
        )
        if not share:
            target_doc = await self._fetch_one(
                select(mdt.c.id, mdt.c.patient_id).where(mdt.c.id == doc_uuid),
                C.MEDICAL_DOCUMENTS,
            )
            target_patient_id = target_doc["patient_id"] if target_doc else None
            valid_doc_id = target_doc["id"] if target_doc else None
            await self.record_audit(
                actor_id=doctor["user_id"],
                actor_role=UserRole.DOCTOR.value,
                patient_id=target_patient_id,
                action=MedicalAuditAction.UNAUTHORIZED_ATTEMPT,
                document_id=valid_doc_id,
                reason="Doctor attempted to view metadata of document without valid consent",
                metadata={"ip": client_ip, "attempted_document_id": doc_uuid, "attempted_doctor_id": doctor_id},
            )
            raise ForbiddenError("You do not have active consent to access this document", code="access_denied")

        doc = await self._fetch_one(
            select(mdt).where(and_(mdt.c.id == doc_uuid, mdt.c.is_deleted.is_(False))),
            C.MEDICAL_DOCUMENTS,
        )
        if not doc:
            raise NotFoundError("Medical document not found", code="document_not_found")

        await self.record_audit(
            actor_id=doctor["user_id"],
            actor_role=UserRole.DOCTOR.value,
            patient_id=doc["patient_id"],
            action=MedicalAuditAction.VIEW,
            document_id=doc_uuid,
            metadata={"ip": client_ip, "title": doc["title"]},
        )
        return doc

    # ------------------------------------------------------------------ Patient Medical Timeline

    async def get_medical_timeline(
        self,
        role: str,
        profile_id: str,
        patient_id: str,
        params: PageParams,
    ) -> tuple[list[dict], int]:
        """Assembles a chronological patient timeline combining:
        - Uploaded medical documents
        - Completed/confirmed appointments
        - Consultation notes (medical records)
        """
        p_id = _parse_uuid(patient_id, allow_hex_miss=True)
        if p_id is None:
            if role == UserRole.DOCTOR.value:
                raise ForbiddenError("You are not authorized to view this patient's medical timeline", code="timeline_forbidden")
            return [], 0

        # Doctor access control: doctor must have at least one appointment OR active share with this patient
        if role == UserRole.DOCTOR.value:
            has_appt = await self._count(
                select(func.count()).select_from(at).where(and_(at.c.patient_id == p_id, at.c.doctor_id == str(profile_id)))
            )
            has_share = await self._count(
                select(func.count()).select_from(dst).where(
                    and_(dst.c.patient_id == p_id, dst.c.doctor_id == str(profile_id), dst.c.consent_status == DocumentConsentStatus.GRANTED.value)
                )
            )
            if has_appt == 0 and has_share == 0:
                raise ForbiddenError("You are not authorized to view this patient's medical timeline", code="timeline_forbidden")

        timeline: list[dict] = []

        # 1. Medical Documents
        doc_clauses = [mdt.c.patient_id == p_id, mdt.c.is_deleted.is_(False)]
        if role == UserRole.DOCTOR.value:
            # Only documents actively shared with this doctor
            doc_stmt = (
                select(mdt)
                .select_from(mdt.join(dst, mdt.c.id == dst.c.document_id))
                .where(and_(*doc_clauses, dst.c.doctor_id == str(profile_id), dst.c.consent_status == DocumentConsentStatus.GRANTED.value))
            )
        else:
            doc_stmt = select(mdt).where(and_(*doc_clauses))

        docs = await self._fetch_all(doc_stmt, C.MEDICAL_DOCUMENTS)
        for d in docs:
            timeline.append({
                "id": f"doc_{d['_id']}",
                "item_type": "DOCUMENT",
                "timestamp": d["created_at"],
                "date": d["created_at"].strftime("%Y-%m-%d") if isinstance(d["created_at"], datetime) else str(d["created_at"])[:10],
                "title": d["title"],
                "category": d["category"],
                "description": d.get("description") or f"Uploaded {d['filename']} ({d['file_type']})",
                "doctor_name": None,
                "status": None,
                "reference_id": d["_id"],
                "metadata": {"filename": d["filename"], "file_size": d["file_size"]},
            })

        # 2. Appointments
        appt_clauses = [at.c.patient_id == p_id]
        if role == UserRole.DOCTOR.value:
            appt_clauses.append(at.c.doctor_id == str(profile_id))

        appts = await self._fetch_all(select(at).where(and_(*appt_clauses)), C.APPOINTMENTS)
        for a in appts:
            timeline.append({
                "id": f"appt_{a['_id']}",
                "item_type": "APPOINTMENT",
                "timestamp": a["start_at"],
                "date": a["appointment_date"],
                "title": f"Consultation with Dr. {a.get('doctor_name', 'Doctor')}",
                "category": a.get("consultation_type"),
                "description": a.get("reason"),
                "doctor_name": a.get("doctor_name"),
                "status": a.get("status"),
                "reference_id": a["_id"],
                "metadata": {"start_time": a.get("start_time"), "end_time": a.get("end_time")},
            })

        # 3. Consultation Notes (Medical Records)
        note_clauses = [mrt.c.patient_id == p_id]
        if role == UserRole.DOCTOR.value:
            note_clauses.append(mrt.c.doctor_id == str(profile_id))

        notes = await self._fetch_all(
            select(mrt, dt.c.name.label("doctor_name"))
            .select_from(mrt.join(dt, mrt.c.doctor_id == dt.c.id, isouter=True))
            .where(and_(*note_clauses)),
            C.MEDICAL_RECORDS,
        )
        for n in notes:
            timeline.append({
                "id": f"note_{n['_id']}",
                "item_type": "CONSULTATION_NOTE",
                "timestamp": n["created_at"],
                "date": n["created_at"].strftime("%Y-%m-%d") if isinstance(n["created_at"], datetime) else str(n["created_at"])[:10],
                "title": f"Doctor Notes from Dr. {n.get('doctor_name', 'Doctor')}",
                "category": "CONSULTATION_NOTE",
                "description": n.get("notes"),
                "doctor_name": n.get("doctor_name"),
                "status": "COMPLETED",
                "reference_id": n["_id"],
                "metadata": {"appointment_id": n.get("appointment_id")},
            })

        # Sort combined timeline descending by timestamp
        timeline.sort(
            key=lambda x: x["timestamp"].isoformat() if isinstance(x["timestamp"], datetime) else str(x["timestamp"]),
            reverse=True,
        )

        total = len(timeline)
        paged = timeline[params.offset : params.offset + params.page_size]
        return paged, total

    # ------------------------------------------------------------------ Audit Log Viewer & Stats

    async def get_audit_history(
        self,
        role: str,
        profile_id: str,
        user_id: str,
        patient_id: str | None = None,
        params: PageParams | None = None,
    ) -> tuple[list[dict], int]:
        """Fetches access audit trail.
        Patients can see their own audits; Admins can see platform audits."""
        clauses = []
        if role == UserRole.PATIENT.value:
            clauses.append(mat.c.patient_id == str(profile_id))
        elif role == UserRole.ADMIN.value:
            if patient_id:
                p_uuid = _parse_uuid(patient_id, allow_hex_miss=True)
                if p_uuid is None:
                    return [], 0
                clauses.append(mat.c.patient_id == p_uuid)
        else:
            raise ForbiddenError("Doctors do not have permission to view audit logs", code="audit_forbidden")

        where_cond = and_(*clauses) if clauses else True
        total = await self._count(select(func.count()).select_from(mat).where(where_cond))

        query = select(mat).where(where_cond).order_by(desc(mat.c.created_at))
        if params:
            query = query.offset(params.offset).limit(params.page_size)

        items = await self._fetch_all(query, C.MEDICAL_RECORD_AUDITS)
        return items, total

    async def get_admin_operational_stats(self) -> dict[str, Any]:
        """Aggregates operational document volume and storage without exposing private contents."""
        total_docs = await self._count(
            select(func.count()).select_from(mdt).where(mdt.c.is_deleted.is_(False))
        )
        sum_size_stmt = select(func.coalesce(func.sum(mdt.c.file_size), 0)).where(mdt.c.is_deleted.is_(False))
        async with self._get_conn() as conn:
            res = await conn.execute(sum_size_stmt)
            total_bytes = res.scalar_one() or 0

        total_shares = await self._count(select(func.count()).select_from(dst))
        active_shares = await self._count(
            select(func.count()).select_from(dst).where(dst.c.consent_status == DocumentConsentStatus.GRANTED.value)
        )

        cat_stmt = (
            select(mdt.c.category, func.count().label("cnt"))
            .where(mdt.c.is_deleted.is_(False))
            .group_by(mdt.c.category)
        )
        cat_counts: dict[str, int] = {}
        async with self._get_conn() as conn:
            res = await conn.execute(cat_stmt)
            for r in res:
                cat_counts[str(r.category)] = r.cnt

        return {
            "total_documents": total_docs,
            "total_size_bytes": total_bytes,
            "total_shares": total_shares,
            "active_shares": active_shares,
            "category_counts": cat_counts,
        }
