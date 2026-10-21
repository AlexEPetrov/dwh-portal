"""Use-cases for editing extraction sources in the DWH registry."""

from __future__ import annotations

from uuid import UUID

from domains.admin.models import ExtractionSourceDraft
from domains.admin.repositories.ports import ExtractionSourceWritePort


class ExtractionSourceAdminService:
    """Application service for admin write operations on extraction sources."""

    def __init__(self, store: ExtractionSourceWritePort) -> None:
        self._store = store

    def get_draft(self, source_id: UUID) -> ExtractionSourceDraft | None:
        """Return an editable draft or ``None`` if the source is missing."""
        return self._store.get_draft(source_id)

    def save_draft(self, draft: ExtractionSourceDraft) -> ExtractionSourceDraft:
        """Persist a draft. Raises until a write adapter is wired."""
        return self._store.save_draft(draft)
