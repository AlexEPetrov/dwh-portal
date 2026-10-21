"""Domain model for portal administration (extraction-source configuration)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID


@dataclass(slots=True)
class ExtractionSourceDraft:
    """Editable view of a registry extraction source before persistence."""

    id: UUID
    name: str
    description: str | None = None
    is_active: bool = True
    extract_source_type_id: int | None = None
    extract_options: dict[str, Any] = field(default_factory=dict)
    storage_options: dict[str, Any] = field(default_factory=dict)
    load_options: dict[str, Any] = field(default_factory=dict)
    data_source_id: UUID | None = None
    load_schedule_id: UUID | None = None
    parent_id: UUID | None = None
    tags: str | None = None
    comment: str | None = None
