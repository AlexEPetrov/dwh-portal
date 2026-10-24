from __future__ import annotations

import datetime
import uuid
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class AssetType(StrEnum):
    DATABASE = "DATABASE"
    SCHEMA = "SCHEMA"
    TABLE = "TABLE"
    VIEW = "VIEW"
    MATERIALIZED_VIEW = "MATERIALIZED_VIEW"
    DATA_SOURCE = "DATA_SOURCE"
    EXTRACTION_SOURCE = "EXTRACTION_SOURCE"
    STORAGE_LOCATION = "STORAGE_LOCATION"
    PROCESS = "PROCESS"


class RelationshipType(StrEnum):
    CONTAINS = "CONTAINS"
    BELONGS_TO = "BELONGS_TO"
    EXTRACTS_TO = "EXTRACTS_TO"
    READS_FROM = "READS_FROM"
    WRITES_TO = "WRITES_TO"
    DERIVED_FROM = "DERIVED_FROM"
    PARENT_OF = "PARENT_OF"


LINEAGE_RELATIONSHIP_TYPES = frozenset(
    {
        RelationshipType.EXTRACTS_TO,
        RelationshipType.READS_FROM,
        RelationshipType.WRITES_TO,
        RelationshipType.DERIVED_FROM,
    }
)


class ChangeType(StrEnum):
    ADDED = "ADDED"
    REMOVED = "REMOVED"
    RENAMED = "RENAMED"
    STRUCTURE_CHANGED = "STRUCTURE_CHANGED"
    DESCRIPTION_CHANGED = "DESCRIPTION_CHANGED"


class CollectorStatus(StrEnum):
    SUCCESS = "SUCCESS"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"
    STALE = "STALE"


class MetadataStatus(StrEnum):
    OK = "OK"
    MISSING = "MISSING"
    INVALID = "INVALID"
    FAILED = "FAILED"
    DEFERRED = "DEFERRED"


class LineageStatus(StrEnum):
    RESOLVED = "RESOLVED"
    UNRESOLVED = "UNRESOLVED"
    PARTIAL = "PARTIAL"


class AssetStatus(StrEnum):
    ACTIVE = "active"
    DELETED = "deleted"


class Asset(BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    asset_type: AssetType
    qualified_name: str
    name: str
    description: str | None = None
    source_provider: str
    native_id: str | None = None
    identity_key: str
    first_seen_at: datetime.datetime
    last_seen_at: datetime.datetime
    deleted_at: datetime.datetime | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)

    @property
    def status(self) -> AssetStatus:
        return AssetStatus.DELETED if self.deleted_at is not None else AssetStatus.ACTIVE


class AssetColumn(BaseModel):
    asset_id: uuid.UUID
    ordinal: int
    name: str
    data_type: str
    nullable: bool = True
    description: str | None = None


class AssetSnapshot(BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    asset_id: uuid.UUID
    snapshot_at: datetime.datetime
    table_bytes: int | None = None
    index_bytes: int | None = None
    total_bytes: int | None = None
    row_estimate: int | None = None
    object_count: int | None = None
    structure_hash: str | None = None

    def contributed_storage_bytes(self) -> tuple[int, int, int]:
        """Bytes this snapshot adds to a history point.

        Zero is treated as missing, matching ``value or fallback``: a stored
        ``total_bytes`` of 0 is replaced by table plus index bytes.
        """
        table_bytes = self.table_bytes or 0
        index_bytes = self.index_bytes or 0
        total_bytes = self.total_bytes or (table_bytes + index_bytes)
        return table_bytes, index_bytes, total_bytes


class AssetListEntry(BaseModel):
    """One catalog-list row: the asset plus the fields the grid renders beside it."""

    asset: Asset
    snapshot: AssetSnapshot | None = None
    last_changed_at: datetime.datetime | None = None


class AssetCountSummary(BaseModel):
    """Active-catalog counts used by the Overview screen."""

    total: int
    tables: int
    views: int


class ChangeCountSummary(BaseModel):
    """Change-event totals for a time window."""

    total: int
    added: int
    changed: int
    removed: int


class SchemaStorageRow(BaseModel):
    schema_name: str
    total_bytes: int
    description: str | None = None


class StorageObjectRow(BaseModel):
    asset_id: uuid.UUID
    qualified_name: str
    display_name: str
    asset_type: AssetType
    total_bytes: int
    table_bytes: int | None = None
    index_bytes: int | None = None
    row_estimate: int | None = None


class StorageSummary(BaseModel):
    """Storage aggregates from the latest snapshot of each sized object."""

    as_of: datetime.datetime | None = None
    table_bytes: int = 0
    index_bytes: int = 0
    total_bytes: int = 0
    by_schema: list[SchemaStorageRow] = Field(default_factory=list)
    largest_objects: list[StorageObjectRow] = Field(default_factory=list)


class Relationship(BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    from_asset_id: uuid.UUID
    to_asset_id: uuid.UUID
    relationship_type: RelationshipType
    source_provider: str
    native_id: str | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)


class ChangeEvent(BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    asset_id: uuid.UUID
    detected_at: datetime.datetime
    change_type: ChangeType
    details: dict[str, Any] = Field(default_factory=dict)


class DiscoveryDiagnostic(BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    asset_id: uuid.UUID | None = None
    detected_at: datetime.datetime
    severity: str
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class CollectionRun(BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    collector_name: str
    started_at: datetime.datetime
    finished_at: datetime.datetime | None = None
    status: CollectorStatus
    message: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class AssetQuery(BaseModel):
    q: str | None = None
    database: str | None = None
    schema_name: str | None = None
    # Single-type filter used by collectors and simple callers.
    asset_type: AssetType | None = None
    # Multi-type filter for the catalog list screen (comma-separated API type=).
    asset_types: list[AssetType] | None = None
    source: str | None = None
    status: AssetStatus = AssetStatus.ACTIVE
    changed_since: datetime.datetime | None = None
    sort: str = "qualified_name"
    page: int = 1
    page_size: int = 50


class ChangeQuery(BaseModel):
    change_type: ChangeType | None = None
    since: datetime.datetime | None = None
    until: datetime.datetime | None = None
    asset_id: uuid.UUID | None = None
    page: int = 1
    page_size: int = 50
