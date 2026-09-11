from __future__ import annotations

import datetime

from domains.catalog.models import (
    Asset,
    AssetQuery,
    AssetStatus,
    AssetType,
    ChangeEvent,
    ChangeQuery,
    ChangeType,
    CollectionRun,
    CollectorStatus,
)
from domains.catalog.repositories.ports import PortalStore

TRACKED_TYPES = {AssetType.TABLE, AssetType.VIEW, AssetType.MATERIALIZED_VIEW}


class ChangeCollector:
    """Compare catalog snapshots and emit structural change events."""

    def __init__(self, store: PortalStore):
        self._store = store

    def run(self, now: datetime.datetime | None = None) -> CollectionRun:
        started = now or datetime.datetime.now(datetime.timezone.utc)
        created = 0
        assets, _ = self._store.list_assets(
            AssetQuery(status=AssetStatus.ACTIVE, page=1, page_size=10_000)
        )
        deleted, _ = self._store.list_assets(
            AssetQuery(status=AssetStatus.DELETED, page=1, page_size=10_000)
        )
        for asset in assets + deleted:
            if asset.asset_type not in TRACKED_TYPES:
                continue
            created += self._detect_for_asset(asset, started)
        run = CollectionRun(
            collector_name="changes",
            started_at=started,
            finished_at=datetime.datetime.now(datetime.timezone.utc),
            status=CollectorStatus.SUCCESS,
            message=f"Created {created} change events",
            details={"events": created},
        )
        return self._store.add_collection_run(run)

    def _detect_for_asset(self, asset: Asset, now: datetime.datetime) -> int:
        snapshots = self._store.list_snapshots(asset_id=asset.id)
        if not snapshots:
            return 0
        latest = snapshots[-1]
        previous = snapshots[-2] if len(snapshots) > 1 else None
        existing, _ = self._store.list_changes(ChangeQuery(asset_id=asset.id, page=1, page_size=50))
        created = 0
        if previous is None and asset.deleted_at is None:
            if not any(event.change_type == ChangeType.ADDED for event in existing):
                self._emit(
                    asset.id,
                    now,
                    ChangeType.ADDED,
                    {
                        "summary": f"New {asset.asset_type.value.lower()}: {asset.name}",
                        "name": asset.name,
                        "qualified_name": asset.qualified_name,
                        "asset_type": asset.asset_type.value,
                    },
                )
                created += 1
        if asset.deleted_at is not None:
            if not any(event.change_type == ChangeType.REMOVED for event in existing):
                self._emit(
                    asset.id,
                    now,
                    ChangeType.REMOVED,
                    {
                        "summary": f"Removed {asset.asset_type.value.lower()}: {asset.name}",
                        "name": asset.name,
                        "qualified_name": asset.qualified_name,
                        "asset_type": asset.asset_type.value,
                    },
                )
                created += 1
            return created
        if previous and latest.structure_hash and previous.structure_hash != latest.structure_hash:
            self._emit(
                asset.id,
                now,
                ChangeType.STRUCTURE_CHANGED,
                {
                    "previous_hash": previous.structure_hash,
                    "current_hash": latest.structure_hash,
                },
            )
            created += 1
        previous_name = asset.attributes.get("previous_name")
        if previous_name and previous_name != asset.name:
            self._emit(
                asset.id,
                now,
                ChangeType.RENAMED,
                {"from": previous_name, "to": asset.name, "native_id": asset.native_id},
            )
            created += 1
        previous_description = asset.attributes.get("previous_description")
        if previous_description is not None and previous_description != asset.description:
            self._emit(
                asset.id,
                now,
                ChangeType.DESCRIPTION_CHANGED,
                {"from": previous_description, "to": asset.description},
            )
            created += 1
        return created

    def _emit(self, asset_id, now: datetime.datetime, change_type: ChangeType, details: dict) -> None:
        self._store.add_change(
            ChangeEvent(asset_id=asset_id, detected_at=now, change_type=change_type, details=details)
        )
