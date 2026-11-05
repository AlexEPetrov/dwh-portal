from __future__ import annotations

import datetime

from domains.catalog.models import CollectionRun, CollectorStatus
from domains.catalog.repositories.ports import PortalStore


class StorageCollector:
    """Record storage freshness without a second size snapshot.

    The catalog collector already stores table, index, total bytes and the
    row estimate on the same row as ``structure_hash``. A later snapshot in
    the same run has no hash and becomes the latest row, so change detection
    skips ``STRUCTURE_CHANGED``.
    """

    def __init__(self, store: PortalStore):
        self._store = store

    def run(self, now: datetime.datetime | None = None) -> CollectionRun:
        """Mark the storage collect complete using the catalog size snapshot."""
        started = now or datetime.datetime.now(datetime.timezone.utc)
        run = CollectionRun(
            collector_name="storage",
            started_at=started,
            finished_at=datetime.datetime.now(datetime.timezone.utc),
            status=CollectorStatus.SUCCESS,
            message="Size metrics stay on the catalog snapshot",
            details={"snapshots": 0, "recorded_by": "catalog"},
        )
        return self._store.add_collection_run(run)
