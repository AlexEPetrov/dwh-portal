"""Domain model for document intake."""

from __future__ import annotations

import datetime
from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID


class DocumentUploadStatus(StrEnum):
    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    FAILED = "FAILED"


@dataclass(slots=True)
class DocumentUploadRequest:
    """A user-initiated document upload intent."""

    id: UUID
    original_filename: str
    content_type: str | None
    size_bytes: int | None
    status: DocumentUploadStatus
    created_at: datetime.datetime
    message: str | None = None
