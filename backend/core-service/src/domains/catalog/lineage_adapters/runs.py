from __future__ import annotations

import datetime

from domains.catalog.models import CollectionRun, CollectorStatus
from domains.catalog.repositories.ports import PortalStore


def record_adapter_run(
    store: PortalStore,
    *,
    name: str,
    started: datetime.datetime,
    status: CollectorStatus,
    message: str,
    details: dict | None = None,
) -> CollectionRun:
    """Persist a per-adapter collection run."""
    run = CollectionRun(
        collector_name=name,
        started_at=started,
        finished_at=datetime.datetime.now(datetime.timezone.utc),
        status=status,
        message=message,
        details=details or {},
    )
    return store.add_collection_run(run)


def skipped_run(
    store: PortalStore,
    *,
    name: str,
    started: datetime.datetime,
    reason: str,
    message: str,
) -> CollectionRun:
    """Optional source is absent: SUCCESS with skipped details, not FAILED."""
    return record_adapter_run(
        store,
        name=name,
        started=started,
        status=CollectorStatus.SUCCESS,
        message=message,
        details={"skipped": True, "reason": reason},
    )
