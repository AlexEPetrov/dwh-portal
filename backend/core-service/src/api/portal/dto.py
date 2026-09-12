from __future__ import annotations

import datetime
import uuid
from typing import Any, Literal

from pydantic import BaseModel, Field

from domains.catalog.models import Asset, AssetColumn, AssetSnapshot, ChangeEvent, Relationship


class FreshnessItem(BaseModel):
    collector_name: str
    status: str
    started_at: datetime.datetime | None = None
    finished_at: datetime.datetime | None = None
    message: str | None = None


class AssetCounts(BaseModel):
    total: int
    tables: int
    views: int


class StorageTotals(BaseModel):
    total_bytes: int
    table_bytes: int
    index_bytes: int


class SchemaStorageRow(BaseModel):
    schema_name: str
    total_bytes: int


class ChangeSummaryItem(BaseModel):
    id: uuid.UUID
    asset_id: uuid.UUID
    change_type: str
    detected_at: datetime.datetime
    details: dict[str, Any] = Field(default_factory=dict)
    asset_type: str | None = None
    display_name: str | None = None
    qualified_name: str | None = None
    name: str | None = None
    status: str | None = None


class RecentChanges(BaseModel):
    total: int
    added: int
    changed: int
    removed: int
    items: list[ChangeSummaryItem]


class OverviewResponse(BaseModel):
    asset_counts: AssetCounts
    storage_totals: StorageTotals
    recent_changes: RecentChanges
    collector_freshness: list[FreshnessItem]
    storage_by_schema: list[SchemaStorageRow]


class SnapshotMetrics(BaseModel):
    table_bytes: int | None = None
    index_bytes: int | None = None
    total_bytes: int | None = None
    row_estimate: int | None = None
    snapshot_at: datetime.datetime | None = None


class AssetListItem(BaseModel):
    id: uuid.UUID
    asset_type: str
    qualified_name: str
    name: str
    display_name: str
    description: str | None = None
    database: str | None = None
    schema_name: str | None = None
    source_provider: str
    status: str
    last_seen_at: datetime.datetime
    last_changed_at: datetime.datetime | None = None
    metrics: SnapshotMetrics = Field(default_factory=SnapshotMetrics)


class AssetListResponse(BaseModel):
    items: list[AssetListItem]
    total: int
    page: int
    page_size: int
    collector_freshness: list[FreshnessItem]


class AssetDetailResponse(BaseModel):
    id: uuid.UUID
    asset_type: str
    qualified_name: str
    name: str
    display_name: str
    description: str | None = None
    database: str | None = None
    schema_name: str | None = None
    source_provider: str
    native_id: str | None = None
    status: str
    first_seen_at: datetime.datetime
    last_seen_at: datetime.datetime
    attributes: dict[str, Any]
    metrics: SnapshotMetrics
    collector_freshness: list[FreshnessItem]


class ColumnItem(BaseModel):
    ordinal: int
    name: str
    data_type: str
    nullable: bool
    description: str | None = None


class ColumnListResponse(BaseModel):
    items: list[ColumnItem]


class LineageNode(BaseModel):
    id: uuid.UUID
    asset_type: str
    qualified_name: str
    name: str
    display_name: str
    unresolved: bool = False


class LineageEdge(BaseModel):
    id: uuid.UUID
    from_asset_id: uuid.UUID
    to_asset_id: uuid.UUID
    relationship_type: str


class UnresolvedTarget(BaseModel):
    asset_id: str
    qualified_name: str
    target_ref: dict[str, Any] = Field(default_factory=dict)


class LineageResponse(BaseModel):
    asset_id: uuid.UUID
    nodes: list[LineageNode]
    edges: list[LineageEdge]
    unresolved_targets: list[UnresolvedTarget]
    collector_freshness: list[FreshnessItem]


class StorageObjectRow(BaseModel):
    asset_id: uuid.UUID
    qualified_name: str
    display_name: str
    asset_type: str
    total_bytes: int
    table_bytes: int | None = None
    index_bytes: int | None = None
    row_estimate: int | None = None


class StorageResponse(BaseModel):
    as_of: datetime.datetime | None = None
    table_bytes: int
    index_bytes: int
    total_bytes: int
    by_schema: list[SchemaStorageRow]
    largest_objects: list[StorageObjectRow]
    collector_freshness: list[FreshnessItem]


class StorageHistoryPoint(BaseModel):
    snapshot_at: datetime.datetime
    table_bytes: int
    index_bytes: int
    total_bytes: int


class StorageHistoryResponse(BaseModel):
    items: list[StorageHistoryPoint]
    collector_freshness: list[FreshnessItem]


class ChangeListResponse(BaseModel):
    items: list[ChangeSummaryItem]
    total: int
    page: int
    page_size: int
    added: int
    changed: int
    removed: int
    collector_freshness: list[FreshnessItem]


class ChangeDetailResponse(BaseModel):
    id: uuid.UUID
    asset_id: uuid.UUID
    change_type: str
    detected_at: datetime.datetime
    details: dict[str, Any]
    asset_qualified_name: str | None = None


class CollectionStatusResponse(BaseModel):
    items: list[FreshnessItem]


class CollectRequest(BaseModel):
    reset: bool = False
    airflow_lineage_mode: Literal["catalog", "code"] | None = None


class CollectRunItem(BaseModel):
    status: str
    message: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class CollectResponse(BaseModel):
    reset: bool
    airflow_lineage_mode: str
    failed: bool
    runs: dict[str, CollectRunItem]


def freshness_items(rows: list[dict]) -> list[FreshnessItem]:
    return [FreshnessItem.model_validate(row) for row in rows]


def display_name_for(asset: Asset) -> str:
    """Prefer human-readable name over technical qualified_name (often contains UUIDs)."""
    attr_name = asset.attributes.get("display_name")
    if attr_name:
        return str(attr_name)
    if asset.name and asset.name.strip():
        return asset.name
    return asset.qualified_name


def snapshot_metrics(snapshot: AssetSnapshot | None) -> SnapshotMetrics:
    if snapshot is None:
        return SnapshotMetrics()
    return SnapshotMetrics(
        table_bytes=snapshot.table_bytes,
        index_bytes=snapshot.index_bytes,
        total_bytes=snapshot.total_bytes,
        row_estimate=snapshot.row_estimate,
        snapshot_at=snapshot.snapshot_at,
    )


def asset_list_item(asset: Asset, snapshot: AssetSnapshot | None, last_changed_at) -> AssetListItem:
    return AssetListItem(
        id=asset.id,
        asset_type=asset.asset_type.value,
        qualified_name=asset.qualified_name,
        name=asset.name,
        display_name=display_name_for(asset),
        description=asset.description,
        database=asset.attributes.get("database"),
        schema_name=asset.attributes.get("schema"),
        source_provider=asset.source_provider,
        status=asset.status.value,
        last_seen_at=asset.last_seen_at,
        last_changed_at=last_changed_at,
        metrics=snapshot_metrics(snapshot),
    )


def column_item(column: AssetColumn) -> ColumnItem:
    return ColumnItem(
        ordinal=column.ordinal,
        name=column.name,
        data_type=column.data_type,
        nullable=column.nullable,
        description=column.description,
    )


def change_item(event: ChangeEvent, asset: Asset | None = None) -> ChangeSummaryItem:
    details = dict(event.details or {})
    if asset is not None:
        details.setdefault("name", asset.name)
        details.setdefault("qualified_name", asset.qualified_name)
        details.setdefault("asset_type", asset.asset_type.value)
        details.setdefault("display_name", display_name_for(asset))
    return ChangeSummaryItem(
        id=event.id,
        asset_id=event.asset_id,
        change_type=event.change_type.value,
        detected_at=event.detected_at,
        details=details,
        asset_type=asset.asset_type.value if asset else None,
        display_name=display_name_for(asset) if asset else None,
        qualified_name=asset.qualified_name if asset else None,
        name=asset.name if asset else None,
        status=asset.status.value if asset else None,
    )


def lineage_node(asset: Asset) -> LineageNode:
    return LineageNode(
        id=asset.id,
        asset_type=asset.asset_type.value,
        qualified_name=asset.qualified_name,
        name=asset.name,
        display_name=display_name_for(asset),
        unresolved=bool(asset.attributes.get("unresolved")),
    )


def lineage_edge(edge: Relationship) -> LineageEdge:
    return LineageEdge(
        id=edge.id,
        from_asset_id=edge.from_asset_id,
        to_asset_id=edge.to_asset_id,
        relationship_type=edge.relationship_type.value,
    )
