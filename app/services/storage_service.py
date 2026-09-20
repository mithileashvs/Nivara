"""Document storage abstraction.

SmartCare stores only document METADATA (filename, url, type, uploader). File bytes live in external
object storage (S3, GCS, Azure Blob, ...). To integrate one later, implement ``DocumentStorage``
(e.g. add ``create_upload_url`` that returns a pre-signed URL) and return it from ``get_storage``.
"""
from typing import Protocol
from urllib.parse import urlparse

from app.core.config import Settings
from app.core.errors import BadRequestError


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
