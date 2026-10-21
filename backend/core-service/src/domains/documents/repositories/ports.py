"""Ports for document intake persistence and storage."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from domains.documents.models import DocumentUploadRequest


class DocumentUploadPort(Protocol):
    """Accept and track document uploads."""

    def create_pending(
        self,
        *,
        original_filename: str,
        content_type: str | None,
        size_bytes: int | None,
    ) -> DocumentUploadRequest:
        """Register an upload intent before bytes are stored."""
        ...

    def get(self, upload_id: UUID) -> DocumentUploadRequest | None:
        """Load upload status by id."""
        ...
