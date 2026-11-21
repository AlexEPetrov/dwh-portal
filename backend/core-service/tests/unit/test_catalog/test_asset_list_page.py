import datetime

from sqlalchemy.dialects import postgresql

from domains.catalog.models import (
    Asset,
    AssetColumn,
    AssetQuery,
    AssetSnapshot,
    AssetType,
    ChangeEvent,
    ChangeType,
)
from domains.catalog.repositories.sql import SqlPortalStore
from domains.catalog.services.asset_service import AssetService
from infrastructure.db.models.portal import PORTAL_SCHEMA


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
    store.add_change(ChangeEvent(asset_id=asset.id, detected_at=now, change_type=ChangeType.ADDED))
    store.add_change(
        ChangeEvent(asset_id=asset.id, detected_at=later, change_type=ChangeType.STRUCTURE_CHANGED)
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
    sql = " ".join(str(statement.compile(dialect=postgresql.dialect())).split())

    assert "LIMIT" in sql
    assert "OFFSET" in sql
    assert "portal_asset_snapshots" in sql
    assert "portal_change_events" in sql
    assert "snapshot_at" in sql
    assert "detected_at" in sql


def test_search_matches_object_and_column_descriptions_once_with_filters(store, now):
    assets = []
    for index, description in enumerate(["Котировки Аргус", None, None]):
        asset = store.upsert_asset(
            Asset(
                asset_type=AssetType.TABLE,
                qualified_name=f"dwh.raw.assessments_{index}",
                name=f"assessments_{index}",
                description=description,
                source_provider="postgres",
                identity_key=f"assessments-{index}",
                first_seen_at=now,
                last_seen_at=now,
                attributes={"database": "dwh", "schema": "raw"},
            )
        )
        assets.append(asset)
    store.replace_columns(
        assets[1].id,
        [
            AssetColumn(
                asset_id=assets[1].id,
                ordinal=ordinal,
                name=f"value_{ordinal}",
                data_type="numeric",
                description="Цена АРГУС",
            )
            for ordinal in (1, 2)
        ],
    )
    rows, total = store.list_asset_page(AssetQuery(q="аргус", page_size=1))
    assert total == 2
    assert len(rows) == 1
    rows, total = store.list_asset_page(AssetQuery(q="аргус", page=2, page_size=1))
    assert total == 2
    assert rows[0].asset.id == assets[1].id
    assert store.list_assets(AssetQuery(q="аргус", schema_name="other"))[1] == 0
    assert store.list_assets(AssetQuery(q="unrelated"))[1] == 0


def test_sql_description_search_uses_correlated_exists_without_duplicate_assets():
    store = SqlPortalStore(session_factory=lambda: None)
    statement = store._filtered_assets(AssetQuery(q="Аргус"))
    compiled = statement.compile(dialect=postgresql.dialect())
    sql = " ".join(str(compiled).split())
    assert "portal_assets.description" in sql
    assert "portal_asset_columns.description" in sql
    assert f"portal_asset_columns.asset_id = {PORTAL_SCHEMA}.portal_assets.id" in sql
    assert "EXISTS (SELECT" in sql
    assert "JOIN" not in sql
    assert "%аргус%" in compiled.params.values()
