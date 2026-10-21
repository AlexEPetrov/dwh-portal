import datetime
import uuid

from domains.catalog.models import (
    Asset,
    AssetSnapshot,
    AssetType,
    ChangeEvent,
    ChangeType,
)
from domains.catalog.services.overview_service import OverviewService
from domains.catalog.services.storage_service import StorageService


def _table(store, now: datetime.datetime, name: str, *, bytes_: int, schema: str = "raw"):
    asset = store.upsert_asset(
        Asset(
            asset_type=AssetType.TABLE,
            qualified_name=f"dwh.{schema}.{name}",
            name=name,
            source_provider="postgres",
            identity_key=f"postgres:dwh.{schema}.{name}",
            first_seen_at=now,
            last_seen_at=now,
            attributes={"database": "dwh", "schema": schema},
        )
    )
    store.add_snapshot(
        AssetSnapshot(
            asset_id=asset.id,
            snapshot_at=now,
            table_bytes=bytes_,
            total_bytes=bytes_,
        )
    )
    return asset


def test_overview_counts_every_active_asset(store, now):
    for index in range(12):
        _table(store, now, f"table_{index}", bytes_=100)
    store.upsert_asset(
        Asset(
            asset_type=AssetType.VIEW,
            qualified_name="dwh.raw.v_sample",
            name="v_sample",
            source_provider="postgres",
            identity_key="postgres:dwh.raw.v_sample",
            first_seen_at=now,
            last_seen_at=now,
            attributes={"database": "dwh", "schema": "raw"},
        )
    )

    overview = OverviewService(store).get_overview()

    assert overview["asset_counts"]["total"] == 13
    assert overview["asset_counts"]["tables"] == 12
    assert overview["asset_counts"]["views"] == 1
    assert overview["storage_totals"]["total_bytes"] == 1_200


def test_storage_totals_ignore_list_page_cap(store, now):
    for index in range(30):
        _table(store, now, f"big_{index}", bytes_=1_000, schema="raw" if index < 20 else "hist")

    storage = StorageService(store).current()

    assert storage["total_bytes"] == 30_000
    assert sum(row["total_bytes"] for row in storage["by_schema"]) == 30_000
    assert len(storage["largest_objects"]) == 20
    assert {row["schema_name"] for row in storage["by_schema"]} == {"raw", "hist"}


def test_overview_change_totals_are_not_capped_by_recent_list(store, now):
    asset = _table(store, now, "watched", bytes_=10)
    recent = datetime.datetime.now(datetime.timezone.utc)
    for index in range(25):
        store.add_change(
            ChangeEvent(
                id=uuid.uuid4(),
                asset_id=asset.id,
                detected_at=recent - datetime.timedelta(minutes=index),
                change_type=ChangeType.ADDED if index % 2 == 0 else ChangeType.STRUCTURE_CHANGED,
            )
        )

    overview = OverviewService(store).get_overview()

    assert overview["recent_changes"]["total"] == 25
    assert overview["recent_changes"]["added"] == 13
    assert overview["recent_changes"]["changed"] == 12
    assert overview["recent_changes"]["removed"] == 0
    assert len(overview["recent_changes"]["items"]) == 8
