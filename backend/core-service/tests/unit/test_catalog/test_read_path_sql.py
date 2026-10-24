import datetime
import uuid

from sqlalchemy.dialects import postgresql

from domains.catalog.models import (
    Asset,
    AssetSnapshot,
    AssetType,
    ChangeQuery,
    ChangeType,
)
from domains.catalog.repositories.sql import SqlPortalStore
from domains.catalog.services.storage_service import StorageService


def _sql(statement) -> str:
    return " ".join(str(statement.compile(dialect=postgresql.dialect())).split())


def test_changes_page_is_limited_in_sql():
    query = ChangeQuery(
        change_type=ChangeType.ADDED,
        asset_id=uuid.uuid4(),
        since=datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc),
        page=2,
        page_size=20,
    )
    page = _sql(SqlPortalStore._changes_page_stmt(query))
    count = _sql(SqlPortalStore._changes_count_stmt(query))

    assert "LIMIT" in page
    assert "OFFSET" in page
    assert "ORDER BY" in page
    assert "detected_at" in page
    assert "count" in count
    assert "LIMIT" not in count


def test_latest_runs_reads_one_row_per_collector():
    sql = _sql(SqlPortalStore._latest_runs_stmt())

    assert "DISTINCT ON" in sql
    assert "portal_collection_runs" in sql
    assert "collector_name" in sql
    assert "started_at" in sql


def test_storage_history_is_grouped_in_sql():
    statement = SqlPortalStore._storage_history_stmt(
        since=datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc)
    )
    sql = _sql(statement).lower()

    assert "group by" in sql
    assert "snapshot_at" in sql
    assert "nullif" in sql
    assert "sum(" in sql
    assert "portal_asset_snapshots" in sql


def test_history_treats_zero_total_bytes_as_missing(store, now):
    first = store.upsert_asset(
        Asset(
            asset_type=AssetType.TABLE,
            qualified_name="dwh.raw.one",
            name="one",
            source_provider="postgres",
            identity_key="postgres:dwh.raw.one",
            first_seen_at=now,
            last_seen_at=now,
        )
    )
    second = store.upsert_asset(
        Asset(
            asset_type=AssetType.TABLE,
            qualified_name="dwh.raw.two",
            name="two",
            source_provider="postgres",
            identity_key="postgres:dwh.raw.two",
            first_seen_at=now,
            last_seen_at=now,
        )
    )
    later = now + datetime.timedelta(days=1)
    store.add_snapshot(
        AssetSnapshot(
            asset_id=first.id,
            snapshot_at=now,
            table_bytes=10,
            index_bytes=2,
            total_bytes=0,
        )
    )
    store.add_snapshot(
        AssetSnapshot(
            asset_id=second.id,
            snapshot_at=now,
            table_bytes=None,
            index_bytes=5,
            total_bytes=None,
        )
    )
    store.add_snapshot(
        AssetSnapshot(
            asset_id=first.id,
            snapshot_at=later,
            table_bytes=1,
            index_bytes=1,
            total_bytes=8,
        )
    )

    points = StorageService(store).history()

    assert points[0]["snapshot_at"] == now
    assert points[0]["table_bytes"] == 10
    assert points[0]["index_bytes"] == 7
    assert points[0]["total_bytes"] == 17
    assert points[1]["total_bytes"] == 8
