from __future__ import annotations

import datetime
import threading
import uuid
from collections import defaultdict

from domains.catalog.models import (
    Asset,
    AssetColumn,
    AssetCountSummary,
    AssetListEntry,
    AssetQuery,
    AssetSnapshot,
    AssetStatus,
    AssetType,
    ChangeCountSummary,
    ChangeEvent,
    ChangeQuery,
    ChangeType,
    CollectionRun,
    DiscoveryDiagnostic,
    Relationship,
    RelationshipType,
    SchemaStorageRow,
    StorageObjectRow,
    StorageSummary,
)
from domains.catalog.search import compact_catalog_text

_STORAGE_TYPES = {
    AssetType.TABLE,
    AssetType.VIEW,
    AssetType.MATERIALIZED_VIEW,
    AssetType.STORAGE_LOCATION,
}


class InMemoryPortalStore:
    """Process-local snapshot store used by tests and the prototype default."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.assets: dict[uuid.UUID, Asset] = {}
        self.columns: dict[uuid.UUID, list[AssetColumn]] = {}
        self.snapshots: list[AssetSnapshot] = []
        self.relationships: dict[uuid.UUID, Relationship] = {}
        self.changes: dict[uuid.UUID, ChangeEvent] = {}
        self.diagnostics: list[DiscoveryDiagnostic] = []
        self.runs: list[CollectionRun] = []
        self._identity_index: dict[tuple[str, str], uuid.UUID] = {}
        self._relationship_index: dict[tuple[uuid.UUID, uuid.UUID, str], uuid.UUID] = {}

    def upsert_asset(self, asset: Asset) -> Asset:
        with self._lock:
            existing_id = self._identity_index.get((asset.source_provider, asset.identity_key))
            if existing_id is not None:
                existing = self.assets[existing_id]
                asset.id = existing.id
                asset.first_seen_at = existing.first_seen_at
            self.assets[asset.id] = asset
            self._identity_index[(asset.source_provider, asset.identity_key)] = asset.id
            return asset.model_copy(deep=True)

    def get_asset(self, asset_id: uuid.UUID, *, include_deleted: bool = True) -> Asset | None:
        asset = self.assets.get(asset_id)
        if asset is None:
            return None
        if not include_deleted and asset.deleted_at is not None:
            return None
        return asset.model_copy(deep=True)

    def get_assets(self, asset_ids: set[uuid.UUID]) -> list[Asset]:
        """Return the requested assets, including soft-deleted rows, in one pass."""
        if not asset_ids:
            return []
        return [
            asset.model_copy(deep=True)
            for asset_id, asset in self.assets.items()
            if asset_id in asset_ids
        ]

    def find_by_identity(self, source_provider: str, identity_key: str) -> Asset | None:
        asset_id = self._identity_index.get((source_provider, identity_key))
        if asset_id is None:
            return None
        return self.get_asset(asset_id)

    def find_by_qualified_name(
        self, qualified_name: str, *, include_deleted: bool = False
    ) -> Asset | None:
        for asset in self.assets.values():
            if asset.qualified_name == qualified_name and (
                include_deleted or asset.deleted_at is None
            ):
                return asset.model_copy(deep=True)
        return None

    def list_assets(self, query: AssetQuery) -> tuple[list[Asset], int]:
        items = list(self.assets.values())
        if query.status == AssetStatus.ACTIVE:
            items = [item for item in items if item.deleted_at is None]
        elif query.status == AssetStatus.DELETED:
            items = [item for item in items if item.deleted_at is not None]
        if query.asset_types:
            allowed = set(query.asset_types)
            items = [item for item in items if item.asset_type in allowed]
        elif query.asset_type is not None:
            items = [item for item in items if item.asset_type == query.asset_type]
        if query.source:
            items = [item for item in items if item.source_provider == query.source]
        if query.database:
            items = [
                item
                for item in items
                if item.attributes.get("database") == query.database
                or item.qualified_name.startswith(f"{query.database}.")
                or item.name == query.database
            ]
        if query.schema_name:
            items = [
                item
                for item in items
                if item.attributes.get("schema") == query.schema_name
                or f".{query.schema_name}." in f".{item.qualified_name}."
            ]
        if query.q:
            needle = compact_catalog_text(query.q)
            items = [
                item
                for item in items
                if needle in compact_catalog_text(item.qualified_name)
                or needle in compact_catalog_text(item.name)
                or needle in compact_catalog_text(item.description)
                or any(
                    needle in compact_catalog_text(column.description)
                    for column in self.columns.get(item.id, [])
                )
            ]
        if query.changed_since is not None:
            changed_ids = {
                event.asset_id
                for event in self.changes.values()
                if event.detected_at >= query.changed_since
            }
            items = [item for item in items if item.id in changed_ids]
        reverse = query.sort.startswith("-")
        sort_key = query.sort.lstrip("-")
        items.sort(key=lambda item: getattr(item, sort_key, item.qualified_name), reverse=reverse)
        total = len(items)
        start = max(query.page - 1, 0) * query.page_size
        page_items = [item.model_copy(deep=True) for item in items[start : start + query.page_size]]
        return page_items, total

    def list_asset_page(self, query: AssetQuery) -> tuple[list[AssetListEntry], int]:
        assets, total = self.list_assets(query)
        return [
            AssetListEntry(
                asset=asset,
                snapshot=self.latest_snapshot(asset.id),
                last_changed_at=self._latest_change_at(asset.id),
            )
            for asset in assets
        ], total

    def count_assets(self) -> AssetCountSummary:
        active = [item for item in self.assets.values() if item.deleted_at is None]
        tables = sum(1 for item in active if item.asset_type == AssetType.TABLE)
        views = sum(
            1 for item in active if item.asset_type in {AssetType.VIEW, AssetType.MATERIALIZED_VIEW}
        )
        by_type = {kind.value: 0 for kind in AssetType}
        for item in active:
            by_type[item.asset_type.value] += 1
        return AssetCountSummary(total=len(active), tables=tables, views=views, by_type=by_type)

    def summarize_storage(self, *, largest_limit: int = 20) -> StorageSummary:
        by_schema: dict[str, int] = defaultdict(int)
        largest: list[StorageObjectRow] = []
        table_bytes = 0
        index_bytes = 0
        total_bytes = 0
        as_of: datetime.datetime | None = None
        for asset in self.assets.values():
            if asset.deleted_at is not None or asset.asset_type not in _STORAGE_TYPES:
                continue
            snapshot = self.latest_snapshot(asset.id)
            if snapshot is None:
                continue
            as_of = snapshot.snapshot_at if as_of is None else max(as_of, snapshot.snapshot_at)
            table_bytes += snapshot.table_bytes or 0
            index_bytes += snapshot.index_bytes or 0
            item_total = snapshot.total_bytes or (snapshot.table_bytes or 0) + (
                snapshot.index_bytes or 0
            )
            total_bytes += item_total
            schema_name = asset.attributes.get("schema") or asset.asset_type.value
            by_schema[str(schema_name)] += item_total
            largest.append(
                StorageObjectRow(
                    asset_id=asset.id,
                    qualified_name=asset.qualified_name,
                    display_name=str(asset.attributes.get("display_name") or asset.qualified_name),
                    asset_type=asset.asset_type,
                    total_bytes=item_total,
                    table_bytes=snapshot.table_bytes,
                    index_bytes=snapshot.index_bytes,
                    row_estimate=snapshot.row_estimate,
                )
            )
        largest.sort(key=lambda item: item.total_bytes, reverse=True)
        schema_rows = [
            SchemaStorageRow(schema_name=name, total_bytes=size)
            for name, size in sorted(by_schema.items(), key=lambda item: item[1], reverse=True)
        ]
        return StorageSummary(
            as_of=as_of,
            table_bytes=table_bytes,
            index_bytes=index_bytes,
            total_bytes=total_bytes,
            by_schema=schema_rows,
            largest_objects=largest[:largest_limit],
        )

    def count_changes(
        self,
        *,
        since: datetime.datetime | None = None,
        until: datetime.datetime | None = None,
    ) -> ChangeCountSummary:
        items = list(self.changes.values())
        if since is not None:
            items = [item for item in items if item.detected_at >= since]
        if until is not None:
            items = [item for item in items if item.detected_at <= until]
        added = sum(1 for item in items if item.change_type == ChangeType.ADDED)
        removed = sum(1 for item in items if item.change_type == ChangeType.REMOVED)
        return ChangeCountSummary(
            total=len(items),
            added=added,
            changed=len(items) - added - removed,
            removed=removed,
        )

    def schema_descriptions(self) -> dict[str, str]:
        descriptions: dict[str, str] = {}
        for item in self.assets.values():
            if item.deleted_at is not None or item.asset_type != AssetType.SCHEMA:
                continue
            if not item.description:
                continue
            name = item.attributes.get("schema") or item.name
            if isinstance(name, str):
                descriptions[name] = item.description
        return descriptions

    def _latest_change_at(self, asset_id: uuid.UUID) -> datetime.datetime | None:
        events, _ = self.list_changes(ChangeQuery(asset_id=asset_id, page=1, page_size=1))
        return events[0].detected_at if events else None

    def replace_columns(self, asset_id: uuid.UUID, columns: list[AssetColumn]) -> None:
        with self._lock:
            self.columns[asset_id] = [column.model_copy(deep=True) for column in columns]

    def get_columns(self, asset_id: uuid.UUID) -> list[AssetColumn]:
        columns = self.columns.get(asset_id, [])
        return [
            column.model_copy(deep=True)
            for column in sorted(columns, key=lambda item: item.ordinal)
        ]

    def add_snapshot(self, snapshot: AssetSnapshot) -> AssetSnapshot:
        with self._lock:
            self.snapshots.append(snapshot.model_copy(deep=True))
            return snapshot

    def latest_snapshot(self, asset_id: uuid.UUID) -> AssetSnapshot | None:
        matches = [item for item in self.snapshots if item.asset_id == asset_id]
        if not matches:
            return None
        latest = max(matches, key=lambda item: item.snapshot_at)
        return latest.model_copy(deep=True)

    def recent_snapshots(self, asset_id: uuid.UUID, *, limit: int = 2) -> list[AssetSnapshot]:
        """Return the newest snapshots for one asset, newest first."""
        matches = [item for item in self.snapshots if item.asset_id == asset_id]
        matches.sort(key=lambda item: item.snapshot_at, reverse=True)
        return [item.model_copy(deep=True) for item in matches[:limit]]

    def list_snapshots(
        self,
        *,
        asset_id: uuid.UUID | None = None,
        since: datetime.datetime | None = None,
        until: datetime.datetime | None = None,
    ) -> list[AssetSnapshot]:
        items = self.snapshots
        if asset_id is not None:
            items = [item for item in items if item.asset_id == asset_id]
        if since is not None:
            items = [item for item in items if item.snapshot_at >= since]
        if until is not None:
            items = [item for item in items if item.snapshot_at <= until]
        items = sorted(items, key=lambda item: item.snapshot_at)
        return [item.model_copy(deep=True) for item in items]

    def aggregate_storage_history(
        self,
        *,
        since: datetime.datetime | None = None,
        until: datetime.datetime | None = None,
    ) -> list[dict]:
        """Sum snapshot bytes by ``snapshot_at`` using the same zero-as-missing rule as SQL."""
        buckets: dict[datetime.datetime, dict[str, int]] = {}
        for snapshot in self.list_snapshots(since=since, until=until):
            table_bytes, index_bytes, total_bytes = snapshot.contributed_storage_bytes()
            bucket = buckets.setdefault(
                snapshot.snapshot_at, {"table_bytes": 0, "index_bytes": 0, "total_bytes": 0}
            )
            bucket["table_bytes"] += table_bytes
            bucket["index_bytes"] += index_bytes
            bucket["total_bytes"] += total_bytes
        return [
            {"snapshot_at": moment, **values}
            for moment, values in sorted(buckets.items(), key=lambda item: item[0])
        ]

    def upsert_relationship(self, relationship: Relationship) -> Relationship:
        with self._lock:
            key = (
                relationship.from_asset_id,
                relationship.to_asset_id,
                str(relationship.relationship_type),
            )
            existing_id = self._relationship_index.get(key)
            if existing_id is not None:
                relationship.id = existing_id
            self.relationships[relationship.id] = relationship.model_copy(deep=True)
            self._relationship_index[key] = relationship.id
            return relationship

    def list_relationships(
        self,
        *,
        asset_id: uuid.UUID | None = None,
        types: set[RelationshipType] | None = None,
    ) -> list[Relationship]:
        items = list(self.relationships.values())
        if asset_id is not None:
            items = [
                item
                for item in items
                if item.from_asset_id == asset_id or item.to_asset_id == asset_id
            ]
        if types is not None:
            items = [item for item in items if item.relationship_type in types]
        return [item.model_copy(deep=True) for item in items]

    def add_change(self, event: ChangeEvent) -> ChangeEvent:
        with self._lock:
            self.changes[event.id] = event.model_copy(deep=True)
            return event

    def get_change(self, change_id: uuid.UUID) -> ChangeEvent | None:
        event = self.changes.get(change_id)
        return event.model_copy(deep=True) if event else None

    def list_changes(self, query: ChangeQuery) -> tuple[list[ChangeEvent], int]:
        items = list(self.changes.values())
        if query.change_type is not None:
            items = [item for item in items if item.change_type == query.change_type]
        if query.since is not None:
            items = [item for item in items if item.detected_at >= query.since]
        if query.until is not None:
            items = [item for item in items if item.detected_at <= query.until]
        if query.asset_id is not None:
            items = [item for item in items if item.asset_id == query.asset_id]
        items.sort(key=lambda item: item.detected_at, reverse=True)
        total = len(items)
        start = max(query.page - 1, 0) * query.page_size
        page_items = [item.model_copy(deep=True) for item in items[start : start + query.page_size]]
        return page_items, total

    def add_diagnostic(self, diagnostic: DiscoveryDiagnostic) -> DiscoveryDiagnostic:
        with self._lock:
            self.diagnostics.append(diagnostic.model_copy(deep=True))
            return diagnostic

    def list_diagnostics(self, asset_id: uuid.UUID | None = None) -> list[DiscoveryDiagnostic]:
        items = self.diagnostics
        if asset_id is not None:
            items = [item for item in items if item.asset_id == asset_id]
        return [item.model_copy(deep=True) for item in items]

    def add_collection_run(self, run: CollectionRun) -> CollectionRun:
        with self._lock:
            self.runs.append(run.model_copy(deep=True))
            return run

    def latest_runs(self) -> list[CollectionRun]:
        latest: dict[str, CollectionRun] = {}
        for run in sorted(self.runs, key=lambda item: item.started_at):
            latest[run.collector_name] = run
        return [item.model_copy(deep=True) for item in latest.values()]

    def mark_missing_as_deleted(
        self,
        source_provider: str,
        seen_ids: set[uuid.UUID],
        deleted_at: datetime.datetime,
        asset_types: set[str] | None = None,
    ) -> list[Asset]:
        removed: list[Asset] = []
        with self._lock:
            for asset in self.assets.values():
                if asset.source_provider != source_provider or asset.deleted_at is not None:
                    continue
                if asset_types and asset.asset_type.value not in asset_types:
                    continue
                if asset.id in seen_ids:
                    continue
                asset.deleted_at = deleted_at
                removed.append(asset.model_copy(deep=True))
        return removed

    def is_empty(self) -> bool:
        return not self.assets

    def purge(self) -> None:
        """Drop all in-memory portal snapshots."""
        with self._lock:
            self.assets.clear()
            self.columns.clear()
            self.snapshots.clear()
            self.relationships.clear()
            self.changes.clear()
            self.diagnostics.clear()
            self.runs.clear()
            self._identity_index.clear()
            self._relationship_index.clear()
