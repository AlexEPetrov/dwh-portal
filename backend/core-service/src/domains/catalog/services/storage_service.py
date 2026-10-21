from __future__ import annotations

import datetime
from collections import defaultdict

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
        snapshots = self._store.list_snapshots(since=since)
        buckets: dict[datetime.datetime, dict[str, int]] = defaultdict(
            lambda: {"table_bytes": 0, "index_bytes": 0, "total_bytes": 0}
        )
        for snapshot in snapshots:
            bucket = buckets[snapshot.snapshot_at]
            bucket["table_bytes"] += snapshot.table_bytes or 0
            bucket["index_bytes"] += snapshot.index_bytes or 0
            bucket["total_bytes"] += snapshot.total_bytes or (snapshot.table_bytes or 0) + (
                snapshot.index_bytes or 0
            )
        return [
            {"snapshot_at": moment, **values}
            for moment, values in sorted(buckets.items(), key=lambda item: item[0])
        ]
