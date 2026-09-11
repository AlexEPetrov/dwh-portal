from __future__ import annotations

import datetime

from domains.catalog.models import (
    AssetQuery,
    AssetSnapshot,
    AssetStatus,
    AssetType,
    CollectionRun,
    CollectorStatus,
)
from domains.catalog.providers.metadata import MetadataProvider
from domains.catalog.repositories.ports import PortalStore


class StorageCollector:
    """Write PostgreSQL size snapshots from catalog metrics already collected."""

    def __init__(self, store: PortalStore, provider: MetadataProvider | None = None):
        self._store = store
        self._provider = provider

    def run(self, now: datetime.datetime | None = None) -> CollectionRun:
        started = now or datetime.datetime.now(datetime.timezone.utc)
        details = {"snapshots": 0}
        try:
            if self._provider is not None:
                objects = [
                    item
                    for item in self._provider.list_assets()
                    if item.asset_type in {AssetType.TABLE, AssetType.MATERIALIZED_VIEW}
                ]
                for item in objects:
                    qualified = f"{item.database}.{item.schema}.{item.name}"
                    asset = self._store.find_by_qualified_name(qualified)
                    if asset is None:
                        continue
                    self._store.add_snapshot(
                        AssetSnapshot(
                            asset_id=asset.id,
                            snapshot_at=started,
                            table_bytes=item.table_bytes,
                            index_bytes=item.index_bytes,
                            total_bytes=item.total_bytes,
                            row_estimate=item.row_estimate,
                        )
                    )
                    details["snapshots"] += 1
            else:
                assets, _ = self._store.list_assets(
                    AssetQuery(status=AssetStatus.ACTIVE, page=1, page_size=10_000)
                )
                for asset in assets:
                    latest = self._store.latest_snapshot(asset.id)
                    if latest is None:
                        continue
                    self._store.add_snapshot(
                        latest.model_copy(update={"snapshot_at": started, "id": latest.id})
                    )
                    details["snapshots"] += 1
            status = CollectorStatus.SUCCESS
            message = f"Stored {details['snapshots']} size snapshots"
        except Exception as exc:
            status = CollectorStatus.FAILED
            message = str(exc)
            details["error"] = str(exc)
        run = CollectionRun(
            collector_name="storage",
            started_at=started,
            finished_at=datetime.datetime.now(datetime.timezone.utc),
            status=status,
            message=message,
            details=details,
        )
        return self._store.add_collection_run(run)
