from __future__ import annotations

import datetime

from domains.catalog.models import AssetQuery, AssetStatus, AssetType, ChangeQuery, ChangeType
from domains.catalog.repositories.ports import PortalStore
from domains.catalog.services.collection_status_service import CollectionStatusService
from domains.catalog.services.storage_service import StorageService


class OverviewService:
    """Compose overview aggregates from stored snapshots."""

    def __init__(self, store: PortalStore, stale_after_hours: int = 36):
        self._store = store
        self._storage = StorageService(store)
        self._status = CollectionStatusService(store, stale_after_hours=stale_after_hours)

    def get_overview(self) -> dict:
        """Compose counts, recent changes, and per-schema storage with schema comments."""
        objects, _ = self._store.list_assets(
            AssetQuery(status=AssetStatus.ACTIVE, page=1, page_size=10_000)
        )
        tables = [item for item in objects if item.asset_type == AssetType.TABLE]
        views = [
            item
            for item in objects
            if item.asset_type in {AssetType.VIEW, AssetType.MATERIALIZED_VIEW}
        ]
        since = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=24)
        recent, _ = self._store.list_changes(ChangeQuery(since=since, page=1, page_size=200))
        added = sum(1 for item in recent if item.change_type == ChangeType.ADDED)
        removed = sum(1 for item in recent if item.change_type == ChangeType.REMOVED)
        changed = len(recent) - added - removed
        storage = self._storage.current()
        return {
            "asset_counts": {
                "total": len(objects),
                "tables": len(tables),
                "views": len(views),
            },
            "storage_totals": {
                "total_bytes": storage["total_bytes"],
                "table_bytes": storage["table_bytes"],
                "index_bytes": storage["index_bytes"],
            },
            "recent_changes": {
                "total": len(recent),
                "added": added,
                "changed": changed,
                "removed": removed,
                "items": recent[:8],
            },
            "collector_freshness": self._status.list_status(),
            "storage_by_schema": self._with_schema_descriptions(storage["by_schema"]),
        }

    def _with_schema_descriptions(self, rows: list[dict]) -> list[dict]:
        """Attach each schema asset comment to the matching storage row."""
        schemas, _ = self._store.list_assets(
            AssetQuery(
                asset_type=AssetType.SCHEMA,
                status=AssetStatus.ACTIVE,
                page=1,
                page_size=10_000,
            )
        )
        descriptions: dict[str, str] = {}
        for item in schemas:
            name = item.attributes.get("schema") or item.name
            if isinstance(name, str) and item.description:
                descriptions[name] = item.description
        return [{**row, "description": descriptions.get(row["schema_name"])} for row in rows]
