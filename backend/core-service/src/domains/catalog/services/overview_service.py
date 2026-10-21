from __future__ import annotations

import datetime

from domains.catalog.models import ChangeQuery
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
        """Compose counts, recent changes, and per-schema storage with schema comments.

        Asset and change totals are full-catalog aggregates. The recent-change
        list still returns only the newest eight events for the page.
        """
        counts = self._store.count_assets()
        since = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=24)
        change_counts = self._store.count_changes(since=since)
        recent, _ = self._store.list_changes(ChangeQuery(since=since, page=1, page_size=8))
        storage = self._storage.current()
        descriptions = self._store.schema_descriptions()
        return {
            "asset_counts": {
                "total": counts.total,
                "tables": counts.tables,
                "views": counts.views,
            },
            "storage_totals": {
                "total_bytes": storage["total_bytes"],
                "table_bytes": storage["table_bytes"],
                "index_bytes": storage["index_bytes"],
            },
            "recent_changes": {
                "total": change_counts.total,
                "added": change_counts.added,
                "changed": change_counts.changed,
                "removed": change_counts.removed,
                "items": recent,
            },
            "collector_freshness": self._status.list_status(),
            "storage_by_schema": [
                {**row, "description": descriptions.get(row["schema_name"])}
                for row in storage["by_schema"]
            ],
        }
