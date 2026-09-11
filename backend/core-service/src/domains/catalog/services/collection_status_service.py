from __future__ import annotations

import datetime

from domains.catalog.models import CollectorStatus
from domains.catalog.repositories.ports import PortalStore


class CollectionStatusService:
    """Expose collector freshness without hiding partial failures."""

    def __init__(self, store: PortalStore, stale_after_hours: int = 36):
        self._store = store
        self._stale_after = datetime.timedelta(hours=stale_after_hours)

    def list_status(self) -> list[dict]:
        now = datetime.datetime.now(datetime.timezone.utc)
        rows = []
        for run in self._store.latest_runs():
            status = run.status
            finished_at = run.finished_at or run.started_at
            if finished_at.tzinfo is None:
                finished_at = finished_at.replace(tzinfo=datetime.timezone.utc)
            if now - finished_at > self._stale_after and status != CollectorStatus.FAILED:
                status = CollectorStatus.STALE
            rows.append(
                {
                    "collector_name": run.collector_name,
                    "status": status,
                    "started_at": run.started_at,
                    "finished_at": run.finished_at,
                    "message": run.message,
                    "details": run.details,
                }
            )
        return rows
