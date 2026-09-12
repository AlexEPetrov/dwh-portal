from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

STORAGE_TARGET_TYPES = frozenset(
    {"storage", "storage_location", "s3", "file", "object_store"}
)
# Plain views are never PROCESS write targets (use derived_from → base table).
VIEW_TARGET_TYPES = frozenset({"view"})
# PROCESS may WRITES_TO these relation kinds.
WRITE_RELATION_TYPES = frozenset({"table", "materialized_view"})


@dataclass(frozen=True)
class LoaderTarget:
    type: str
    database: str | None = None
    schema: str | None = None
    name: str | None = None
    path: str | None = None
    # When type is view: VIEW DERIVED_FROM → base table (not PROCESS WRITES_TO).
    derived_from: "LoaderTarget | None" = None


@dataclass(frozen=True)
class LoaderMetadata:
    schema_version: str
    name: str
    description: str | None = None
    writes_to: list[LoaderTarget] = field(default_factory=list)
    reads_from: list[LoaderTarget] = field(default_factory=list)
    metadata_status: str = "OK"
    diagnostic: dict[str, Any] | None = None


@dataclass(frozen=True)
class ExtractionSourceRecord:
    id: str
    name: str | None
    descr: str | None
    access_level: int | None
    is_active: bool | None
    extract_source_type_id: int | None
    extract_options: dict[str, Any]
    storage_options: dict[str, Any]
    load_options: dict[str, Any]
    load_schedule_id: str | None
    data_source_id: str | None
    data_source_name: str | None
    tags: str | None
    parent_id: str | None
    comment: str | None


class LineageProvider(Protocol):
    def list_extraction_sources(self) -> list[ExtractionSourceRecord]: ...

    def resolve_process_metadata(self, handler: dict[str, Any]) -> LoaderMetadata: ...
