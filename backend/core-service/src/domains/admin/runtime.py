"""Composition root for the admin domain."""

from __future__ import annotations

from domains.admin.services.extraction_source_service import ExtractionSourceAdminService


class _UnimplementedExtractionSourceWritePort:
    """Placeholder until DWH registry write adapter is implemented."""

    def get_draft(self, source_id):  # type: ignore[no-untyped-def]
        raise NotImplementedError("Admin registry read/write adapter is not wired yet")

    def save_draft(self, draft):  # type: ignore[no-untyped-def]
        raise NotImplementedError("Admin registry read/write adapter is not wired yet")


def get_extraction_source_admin_service() -> ExtractionSourceAdminService:
    """Return the admin application service (write path not wired yet)."""
    return ExtractionSourceAdminService(_UnimplementedExtractionSourceWritePort())
