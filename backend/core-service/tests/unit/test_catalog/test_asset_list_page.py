import datetime

from sqlalchemy.dialects import postgresql

from domains.catalog.models import (
    Asset,
    AssetQuery,
    AssetSnapshot,
    AssetType,
    ChangeEvent,
    ChangeType,
)
from domains.catalog.repositories.sql import SqlPortalStore
from domains.catalog.services.asset_service import AssetService


def test_list_page_keeps_latest_snapshot_and_change(store, now):
    asset = store.upsert_asset(
        Asset(
            asset_type=AssetType.TABLE,
            qualified_name="dwh.raw.ice_brent",
            name="ice_brent",
            source_provider="postgres",
            identity_key="postgres:dwh.raw.ice_brent",
            first_seen_at=now,
            last_seen_at=now,
            attributes={"database": "dwh", "schema": "raw"},
        )
    )
    later = now + datetime.timedelta(hours=1)
    store.add_snapshot(
        AssetSnapshot(asset_id=asset.id, snapshot_at=now, total_bytes=10, table_bytes=10)
    )
    store.add_snapshot(
        AssetSnapshot(asset_id=asset.id, snapshot_at=later, total_bytes=90, table_bytes=90)
    )
    store.add_change(
        ChangeEvent(asset_id=asset.id, detected_at=now, change_type=ChangeType.ADDED)
    )
    store.add_change(
        ChangeEvent(
            asset_id=asset.id, detected_at=later, change_type=ChangeType.STRUCTURE_CHANGED
        )
    )

    rows, total = AssetService(store).list_page(AssetQuery(q="ice_brent", page_size=10))

    assert total == 1
    assert rows[0].asset.id == asset.id
    assert rows[0].snapshot is not None
    assert rows[0].snapshot.total_bytes == 90
    assert rows[0].last_changed_at == later


def test_list_page_filters_comma_separated_types(store, now):
    for name, asset_type in (
        ("ice_brent", AssetType.TABLE),
        ("v_ice", AssetType.VIEW),
        ("raw", AssetType.SCHEMA),
    ):
        store.upsert_asset(
            Asset(
                asset_type=asset_type,
                qualified_name=f"dwh.raw.{name}",
                name=name,
                source_provider="postgres",
                identity_key=f"postgres:dwh.raw.{name}",
                first_seen_at=now,
                last_seen_at=now,
                attributes={"database": "dwh", "schema": "raw"},
            )
        )

    rows, total = AssetService(store).list_page(
        AssetQuery(
            asset_types=[AssetType.TABLE, AssetType.VIEW],
            page=1,
            page_size=10,
        )
    )

    assert total == 2
    assert {row.asset.asset_type for row in rows} == {AssetType.TABLE, AssetType.VIEW}


def test_sql_list_page_is_a_bounded_select():
    store = SqlPortalStore(session_factory=lambda: None)
    statement = store._asset_page_stmt(
        AssetQuery(q="ice", database="dwh", schema_name="raw", page=2, page_size=25)
    )
    sql = " ".join(
        str(statement.compile(dialect=postgresql.dialect())).split()
    )

    assert "LIMIT" in sql
    assert "OFFSET" in sql
    assert "portal_asset_snapshots" in sql
    assert "portal_change_events" in sql
    assert "snapshot_at" in sql
    assert "detected_at" in sql
