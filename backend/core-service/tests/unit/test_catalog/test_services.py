from domains.catalog.models import (
    LINEAGE_RELATIONSHIP_TYPES,
    AssetQuery,
    AssetStatus,
    AssetType,
    ChangeQuery,
)
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


def test_object_lineage_reads_only_incident_edges_per_level(seeded_store, monkeypatch):
    from uuid import uuid4

    raw = seeded_store.find_by_qualified_name("dwh.raw.ice_brent")
    assert raw is not None
    list_relationships = seeded_store.list_relationships
    expected = list_relationships(asset_id=raw.id)
    expected = [edge for edge in expected if edge.relationship_type in LINEAGE_RELATIONSHIP_TYPES]
    assert expected
    for _ in range(100):
        seeded_store.upsert_relationship(
            expected[0].model_copy(
                update={"id": uuid4(), "from_asset_id": uuid4(), "to_asset_id": uuid4()}
            )
        )

    frontiers = []

    def read_edges(*, asset_ids, types):
        frontiers.append(asset_ids)
        return list_relationships(asset_ids=asset_ids, types=types)

    monkeypatch.setattr(seeded_store, "list_relationships", read_edges)
    result = LineageService(seeded_store, max_depth=2).get_lineage(raw.id)

    neighbours = {
        endpoint for edge in expected for endpoint in (edge.from_asset_id, edge.to_asset_id)
    } - {raw.id}
    assert frontiers == [{raw.id}, neighbours]
    assert {edge.id for edge in result["edges"]} == {
        edge.id
        for edge in list_relationships(
            asset_ids={raw.id} | neighbours, types=set(LINEAGE_RELATIONSHIP_TYPES)
        )
    }


def test_lineage_roots_are_data_sources_and_orphan_extractions(seeded_store):
    import datetime

    from domains.catalog.identity import extraction_source_identity
    from domains.catalog.models import Asset

    now = datetime.datetime(2026, 9, 6, 2, 15, tzinfo=datetime.timezone.utc)
    qualified_name, identity_key = extraction_source_identity("airflow-dag")
    seeded_store.upsert_asset(
        Asset(
            asset_type=AssetType.EXTRACTION_SOURCE,
            qualified_name=qualified_name,
            name="platts_egd",
            identity_key=identity_key,
            source_provider="airflow_dags",
            native_id="airflow-dag",
            first_seen_at=now,
            last_seen_at=now,
        )
    )
    payload = LineageService(seeded_store).list_roots()
    names = {node.name for node in payload["nodes"]}
    types = {node.asset_type for node in payload["nodes"]}
    assert payload["edges"] == []
    assert AssetType.DATA_SOURCE in types
    assert "ICE" in names
    assert "platts_egd" in names
    assert "Brent Settlement" not in names
    ice = next(node for node in payload["nodes"] if node.name == "ICE")
    ice_counts = payload["counts"][ice.id]
    assert ice_counts.get("EXTRACTION_SOURCE", 0) >= 1


def test_overview_and_storage_read_snapshots_only(seeded_store):
    overview = OverviewService(seeded_store).get_overview()
    storage = StorageService(seeded_store).current()
    assert overview["asset_counts"]["tables"] >= 1
    assert storage["total_bytes"] > 0
    assert any(row["schema_name"] == "history" for row in storage["by_schema"])


def test_overview_includes_schema_description(seeded_store):
    schema = seeded_store.find_by_qualified_name("dwh.raw")
    assert schema is not None
    seeded_store.upsert_asset(schema.model_copy(update={"description": "Raw landings"}))
    overview = OverviewService(seeded_store).get_overview()
    row = next(item for item in overview["storage_by_schema"] if item["schema_name"] == "raw")
    assert row["description"] == "Raw landings"
    untitled = next(item for item in overview["storage_by_schema"] if item["schema_name"] == "history")
    assert untitled["description"] is None


def test_changes_are_queryable(seeded_store):
    events, total = seeded_store.list_changes(ChangeQuery(page=1, page_size=20))
    assert total == 3
    assert {event.change_type.value for event in events} == {"ADDED", "STRUCTURE_CHANGED", "REMOVED"}
