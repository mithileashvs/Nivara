"""Document storage abstraction and secure medical document file manager.

Supports:
- Legacy metadata-only URL references (ExternalUrlStorage).
- Secure private object storage with strict file validation (MedicalStorageService):
  - Local secure file storage with path traversal protection.
  - Supabase Storage integration via REST API if configured.
  - Magic byte validation for PDF, JPEG, PNG, WebP, TIFF.
  - Dangerous executable file rejection.
  - File size enforcement.
"""
from __future__ import annotations

import asyncio
import logging
import re
from pathlib import Path
from typing import Protocol
from urllib.parse import urlparse
from uuid import uuid4

import httpx

from app.core.config import Settings
from app.core.errors import BadRequestError, NotFoundError

logger = logging.getLogger("nivara.storage")


class DocumentStorage(Protocol):
    def validate_reference(self, file_url: str) -> str:
        """Validate/normalise a reference to an externally stored file; return the stored URL."""


class ExternalUrlStorage:
    """Accepts references to files already uploaded elsewhere (https only, optional host allow-list)."""

    def __init__(self, allowed_hosts: list[str]) -> None:
        self.allowed_hosts = {h.lower() for h in allowed_hosts}

    def validate_reference(self, file_url: str) -> str:
        parsed = urlparse(file_url)
        if parsed.scheme != "https" or not parsed.hostname:
            raise BadRequestError("file_url must be an https URL", code="invalid_file_url")
        if parsed.username or parsed.password:
            raise BadRequestError("file_url must not contain credentials", code="invalid_file_url")
        if self.allowed_hosts and parsed.hostname.lower() not in self.allowed_hosts:
            raise BadRequestError("file_url host is not an allowed storage host", code="invalid_file_url")
        if len(file_url) > 2048:
            raise BadRequestError("file_url is too long", code="invalid_file_url")
        return file_url


def get_storage(settings: Settings) -> DocumentStorage:
    return ExternalUrlStorage(settings.allowed_document_hosts)


# ---------------------------------------------------------------------------
# Phase 4: Secure Medical Document File Validation & Storage
# ---------------------------------------------------------------------------

ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png", ".webp", ".tiff", ".tif"}


def sanitize_filename(filename: str) -> str:
    """Remove path traversal sequences and unsafe characters from a user-supplied filename."""
    # Keep only filename without directory components
    name = Path(filename).name
    # Replace dangerous characters with underscores
    clean = re.sub(r"[^\w\s\.\-]", "_", name).strip()
    return clean or "document.bin"


def validate_file_content(content: bytes, filename: str, max_bytes: int) -> tuple[str, str]:
    """Validate file content, size, extension and magic bytes.

    Returns:
        tuple of (sanitized_extension, verified_mime_type).
    Raises:
        BadRequestError if validation fails.
    """
    if len(content) == 0:
        raise BadRequestError("Uploaded file is empty", code="empty_file")
    if len(content) > max_bytes:
        max_mb = max_bytes // (1024 * 1024)
        raise BadRequestError(f"File size exceeds maximum allowed limit ({max_mb} MB)", code="file_too_large")

    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise BadRequestError(
            f"Unsupported file extension '{ext}'. Allowed extensions: PDF, JPG, PNG, WEBP, TIFF",
            code="invalid_file_extension",
        )

    # Magic byte verification
    verified_mime: str | None = None
    if content.startswith(b"%PDF-"):
        verified_mime = "application/pdf"
    elif content.startswith(b"\xff\xd8\xff"):
        verified_mime = "image/jpeg"
    elif content.startswith(b"\x89PNG\r\n\x1a\n"):
        verified_mime = "image/png"
    elif content[:4] == b"RIFF" and len(content) >= 12 and content[8:12] == b"WEBP":
        verified_mime = "image/webp"
    elif content[:4] in (b"II*\x00", b"MM\x00*"):
        verified_mime = "image/tiff"

    if verified_mime is None:
        raise BadRequestError(
            "File content does not match any allowed medical document format (PDF, JPEG, PNG, WEBP, TIFF)",
            code="invalid_file_content",
        )

    # Ensure extension matches MIME type
    if verified_mime == "application/pdf" and ext != ".pdf":
        raise BadRequestError("File extension does not match PDF content", code="mime_extension_mismatch")
    if verified_mime == "image/jpeg" and ext not in (".jpg", ".jpeg"):
        raise BadRequestError("File extension does not match JPEG content", code="mime_extension_mismatch")
    if verified_mime == "image/png" and ext != ".png":
        raise BadRequestError("File extension does not match PNG content", code="mime_extension_mismatch")
    if verified_mime == "image/webp" and ext != ".webp":
        raise BadRequestError("File extension does not match WebP content", code="mime_extension_mismatch")
    if verified_mime == "image/tiff" and ext not in (".tiff", ".tif"):
        raise BadRequestError("File extension does not match TIFF content", code="mime_extension_mismatch")

    # Executable content detection
    sample = content[:1024].lower()
    if (
        b"<?php" in sample
        or b"<script" in sample
        or content.startswith(b"#!/")
        or b"eval(" in sample
        or b"<html" in sample
    ):
        raise BadRequestError("File contains potentially dangerous or executable script tags", code="dangerous_file_content")

    return ext, verified_mime


class MedicalStorageService:
    """Manages secure storage of private medical document files."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.base_dir = Path(settings.local_storage_dir).resolve()
        if self.settings.document_storage_provider == "local":
            self.base_dir.mkdir(parents=True, exist_ok=True)

    async def save_file(self, patient_id: str, original_filename: str, content: bytes) -> tuple[str, str, int, str]:
        """Validates and stores a medical file.

        Returns:
            (storage_path, verified_mime_type, file_size, storage_provider)
        """
        ext, mime_type = validate_file_content(content, original_filename, self.settings.max_document_upload_bytes)
        file_id = uuid4().hex
        rel_path = f"patients/{patient_id}/{file_id}{ext}"

        # Supabase Storage (required in production)
        if self.settings.document_storage_provider == "supabase":
            if not (self.settings.supabase_url and self.settings.supabase_service_role_key):
                raise BadRequestError(
                    "Supabase storage is selected but SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY is missing",
                    code="storage_misconfigured",
                )
            try:
                await self._upload_supabase(rel_path, content, mime_type)
                logger.info("Uploaded document %s to Supabase Storage bucket %s", rel_path, self.settings.supabase_storage_bucket)
                return rel_path, mime_type, len(content), "SUPABASE"
            except Exception as exc:  # noqa: BLE001
                logger.error("Supabase storage upload failed: %s", exc)
                raise BadRequestError(
                    "Failed to upload medical document to cloud object storage. Please verify storage configuration.",
                    code="storage_upload_failed",
                )

        # Local secure private storage (development only)
        full_path = (self.base_dir / rel_path).resolve()
        if not str(full_path).startswith(str(self.base_dir)):
            raise BadRequestError("Invalid storage path detected", code="path_traversal")

        full_path.parent.mkdir(parents=True, exist_ok=True)
        await asyncio.to_thread(full_path.write_bytes, content)
        logger.info("Saved document %s to local secure storage", rel_path)
        return rel_path, mime_type, len(content), "LOCAL"

    async def get_file_path(self, storage_path: str) -> Path:
        """Returns the local file Path, ensuring it does not escape base_dir."""
        full_path = (self.base_dir / storage_path).resolve()
        if not str(full_path).startswith(str(self.base_dir)) or not full_path.exists():
            raise NotFoundError("Stored document file not found", code="file_not_found")
        return full_path

    async def read_file_bytes(self, storage_path: str, storage_provider: str = "LOCAL") -> tuple[bytes, str]:
        """Reads file bytes from storage."""
        if storage_provider == "SUPABASE":
            if not (self.settings.supabase_url and self.settings.supabase_service_role_key):
                raise BadRequestError("Supabase storage is not configured to read this document", code="storage_misconfigured")
            try:
                data = await self._download_supabase(storage_path)
                return data, "application/octet-stream"
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 404:
                    raise NotFoundError("Stored document file not found in Supabase Storage", code="file_not_found")
                logger.error("Supabase download failed (%s): %s", exc.response.status_code, exc)
                raise BadRequestError("Unable to retrieve document from Supabase Storage", code="storage_error")
            except Exception as exc:  # noqa: BLE001
                logger.error("Supabase download error: %s", exc)
                raise BadRequestError("Unable to retrieve document from Supabase Storage", code="storage_error")

        path = await self.get_file_path(storage_path)
        data = await asyncio.to_thread(path.read_bytes)
        return data, "application/octet-stream"

    async def delete_file(self, storage_path: str, storage_provider: str = "LOCAL") -> bool:
        """Safely removes file from storage."""
        if (
            storage_provider == "SUPABASE"
            and self.settings.supabase_url
            and self.settings.supabase_service_role_key
        ):
            try:
                await self._delete_supabase(storage_path)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Supabase delete failed: %s", exc)

        try:
            full_path = (self.base_dir / storage_path).resolve()
            if str(full_path).startswith(str(self.base_dir)) and full_path.exists():
                await asyncio.to_thread(full_path.unlink, True)
                return True
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to delete local document file %s: %s", storage_path, exc)
        return False

    # ------------------------------------------------------------------ Supabase Storage REST client
    async def _upload_supabase(self, rel_path: str, content: bytes, mime_type: str) -> None:
        url = f"{str(self.settings.supabase_url).rstrip('/')}/storage/v1/object/{self.settings.supabase_storage_bucket}/{rel_path}"
        key = self.settings.supabase_service_role_key.get_secret_value() if self.settings.supabase_service_role_key else ""
        headers = {
            "Authorization": f"Bearer {key}",
            "apikey": key,
            "Content-Type": mime_type,
            "x-upsert": "true",
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(url, content=content, headers=headers)
            resp.raise_for_status()

    async def _download_supabase(self, rel_path: str) -> bytes:
        url = f"{str(self.settings.supabase_url).rstrip('/')}/storage/v1/object/authenticated/{self.settings.supabase_storage_bucket}/{rel_path}"
        key = self.settings.supabase_service_role_key.get_secret_value() if self.settings.supabase_service_role_key else ""
        headers = {
            "Authorization": f"Bearer {key}",
            "apikey": key,
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            return resp.content

    async def _delete_supabase(self, rel_path: str) -> None:
        url = f"{str(self.settings.supabase_url).rstrip('/')}/storage/v1/object/{self.settings.supabase_storage_bucket}/{rel_path}"
        key = self.settings.supabase_service_role_key.get_secret_value() if self.settings.supabase_service_role_key else ""
        headers = {
            "Authorization": f"Bearer {key}",
            "apikey": key,
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.delete(url, headers=headers)
            resp.raise_for_status()
