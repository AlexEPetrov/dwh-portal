"""Ports for admin persistence (DWH registry writes)."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from domains.admin.models import ExtractionSourceDraft


class ExtractionSourceWritePort(Protocol):
    """Write-side access to ``sys.data_extraction_sources`` (and related)."""

    def get_draft(self, source_id: UUID) -> ExtractionSourceDraft | None:
        """Load a mutable draft by registry id."""
        ...

    def save_draft(self, draft: ExtractionSourceDraft) -> ExtractionSourceDraft:
        """Persist draft fields back to the registry. Not implemented yet."""
        ...
