"""Composition root for the documents domain."""

from __future__ import annotations

from domains.documents.services.upload_service import DocumentUploadService


class _UnimplementedDocumentUploadPort:
    """Placeholder until storage intake adapter is implemented."""

    def create_pending(self, *, original_filename, content_type, size_bytes):  # type: ignore[no-untyped-def]
        raise NotImplementedError("Document upload adapter is not wired yet")

    def get(self, upload_id):  # type: ignore[no-untyped-def]
        raise NotImplementedError("Document upload adapter is not wired yet")


def get_document_upload_service() -> DocumentUploadService:
    """Return the documents application service (intake path not wired yet)."""
    return DocumentUploadService(_UnimplementedDocumentUploadPort())
