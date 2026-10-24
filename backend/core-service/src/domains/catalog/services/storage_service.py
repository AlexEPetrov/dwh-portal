from __future__ import annotations

import datetime

from domains.catalog.repositories.ports import PortalStore


class StorageService:
    """Aggregate storage snapshots without querying live DWH."""

    def __init__(self, store: PortalStore):
        self._store = store

    def current(self) -> dict:
        """Return storage totals, per-schema bytes, and the largest objects.

        Totals cover every active sized object that has a snapshot. They are not
        limited by the catalog list page size.
        """
        summary = self._store.summarize_storage(largest_limit=20)
        return {
            "as_of": summary.as_of,
            "table_bytes": summary.table_bytes,
            "index_bytes": summary.index_bytes,
            "total_bytes": summary.total_bytes,
            "by_schema": [row.model_dump() for row in summary.by_schema],
            "largest_objects": [row.model_dump() for row in summary.largest_objects],
        }

    def history(self, since: datetime.datetime | None = None) -> list[dict]:
        """Return one summed point per snapshot time, without a default time window."""
        return self._store.aggregate_storage_history(since=since)
