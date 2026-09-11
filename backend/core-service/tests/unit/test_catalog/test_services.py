from domains.catalog.models import AssetQuery, AssetStatus, AssetType, ChangeQuery
from domains.catalog.services.asset_service import AssetService
from domains.catalog.services.lineage_service import LineageService
from domains.catalog.services.overview_service import OverviewService
from domains.catalog.services.storage_service import StorageService


def test_asset_search_and_pagination(seeded_store):
    service = AssetService(seeded_store)
    items, total = service.list_assets(
        AssetQuery(q="ice_brent", asset_type=AssetType.TABLE, page=1, page_size=10)
    )
    assert total == 1
    assert items[0].name == "ice_brent"
    page, page_total = service.list_assets(
        AssetQuery(asset_type=AssetType.TABLE, status=AssetStatus.ACTIVE, page=1, page_size=2)
    )
    assert page_total >= 2
    assert len(page) == 2


def test_soft_deleted_table_is_hidden_from_active_list(seeded_store):
    service = AssetService(seeded_store)
    active, _ = service.list_assets(AssetQuery(q="old_ice_prices", status=AssetStatus.ACTIVE))
    deleted, _ = service.list_assets(AssetQuery(q="old_ice_prices", status=AssetStatus.DELETED))
    assert active == []
    assert deleted[0].status.value == "deleted"


def test_lineage_walks_source_to_table_and_keeps_data_flow_only(seeded_store):
    raw = seeded_store.find_by_qualified_name("dwh.raw.ice_brent")
    assert raw is not None
    payload = LineageService(seeded_store).get_lineage(raw.id)
    types = {edge.relationship_type.value for edge in payload["edges"]}
    assert "CONTAINS" not in types
    assert "WRITES_TO" in types
    names = {node.name for node in payload["nodes"]}
    assert {"ICE", "Brent Settlement", "landing/ice/brent", "ice_brent", "market_prices"} <= names


def test_overview_and_storage_read_snapshots_only(seeded_store):
    overview = OverviewService(seeded_store).get_overview()
    storage = StorageService(seeded_store).current()
    assert overview["asset_counts"]["tables"] >= 1
    assert storage["total_bytes"] > 0
    assert any(row["schema_name"] == "history" for row in storage["by_schema"])


def test_changes_are_queryable(seeded_store):
    events, total = seeded_store.list_changes(ChangeQuery(page=1, page_size=20))
    assert total == 3
    assert {event.change_type.value for event in events} == {"ADDED", "STRUCTURE_CHANGED", "REMOVED"}
