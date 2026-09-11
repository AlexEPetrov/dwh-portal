from __future__ import annotations

import datetime
from collections import defaultdict

from domains.catalog.models import AssetQuery, AssetStatus, AssetType
from domains.catalog.repositories.ports import PortalStore

OBJECT_TYPES = {AssetType.TABLE, AssetType.VIEW, AssetType.MATERIALIZED_VIEW, AssetType.STORAGE_LOCATION}


class StorageService:
    """Aggregate storage snapshots without querying live DWH."""

    def __init__(self, store: PortalStore):
        self._store = store

    def current(self) -> dict:
        assets, _ = self._store.list_assets(
            AssetQuery(status=AssetStatus.ACTIVE, page=1, page_size=10_000)
        )
        by_schema: dict[str, int] = defaultdict(int)
        largest: list[dict] = []
        table_bytes = 0
        index_bytes = 0
        total_bytes = 0
        snapshot_at: datetime.datetime | None = None

        for asset in assets:
            if asset.asset_type not in OBJECT_TYPES:
                continue
            snapshot = self._store.latest_snapshot(asset.id)
            if snapshot is None:
                continue
            snapshot_at = snapshot.snapshot_at if snapshot_at is None else max(snapshot_at, snapshot.snapshot_at)
            table_bytes += snapshot.table_bytes or 0
            index_bytes += snapshot.index_bytes or 0
            item_total = snapshot.total_bytes or (snapshot.table_bytes or 0) + (snapshot.index_bytes or 0)
            total_bytes += item_total
            schema_name = asset.attributes.get("schema") or asset.asset_type.value
            by_schema[schema_name] += item_total
            largest.append(
                {
                    "asset_id": asset.id,
                    "qualified_name": asset.qualified_name,
                    "display_name": asset.attributes.get("display_name") or asset.qualified_name,
                    "asset_type": asset.asset_type,
                    "total_bytes": item_total,
                    "table_bytes": snapshot.table_bytes,
                    "index_bytes": snapshot.index_bytes,
                    "row_estimate": snapshot.row_estimate,
                }
            )

        largest.sort(key=lambda item: item["total_bytes"] or 0, reverse=True)
        schema_rows = [
            {"schema_name": name, "total_bytes": size}
            for name, size in sorted(by_schema.items(), key=lambda item: item[1], reverse=True)
        ]
        return {
            "as_of": snapshot_at,
            "table_bytes": table_bytes,
            "index_bytes": index_bytes,
            "total_bytes": total_bytes,
            "by_schema": schema_rows,
            "largest_objects": largest[:20],
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
