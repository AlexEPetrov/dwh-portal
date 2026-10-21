"""Use-cases for document upload / intake."""

from __future__ import annotations

from uuid import UUID

from domains.documents.models import DocumentUploadRequest
from domains.documents.repositories.ports import DocumentUploadPort


class DocumentUploadService:
    """Application service for operational document intake."""

    def __init__(self, store: DocumentUploadPort) -> None:
        self._store = store

    def begin_upload(
        self,
        *,
        original_filename: str,
        content_type: str | None = None,
        size_bytes: int | None = None,
    ) -> DocumentUploadRequest:
        """Start an upload. Raises until a storage adapter is wired."""
        return self._store.create_pending(
            original_filename=original_filename,
            content_type=content_type,
            size_bytes=size_bytes,
        )

    def get_upload(self, upload_id: UUID) -> DocumentUploadRequest | None:
        """Return upload status or ``None``."""
        return self._store.get(upload_id)
