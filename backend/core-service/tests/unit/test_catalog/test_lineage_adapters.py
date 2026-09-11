from domains.catalog.collectors.catalog import CatalogCollector
from domains.catalog.collectors.runner import run_daily_collection
from domains.catalog.identity import airflow_process_identity, url_data_source_identity
from domains.catalog.lineage_adapters.airflow_dags import (
    AirflowDagsLineageAdapter,
    normalize_url,
)
from domains.catalog.lineage_adapters.postgres_sql import PostgresSqlLineageAdapter
from domains.catalog.lineage_adapters.registry import load_lineage_adapters
from domains.catalog.models import AssetType, CollectorStatus, RelationshipType
from domains.catalog.providers.extraction_registry import ExtractionRegistryMissing
from domains.catalog.providers.metadata import CatalogObject, RelationDependency
from domains.catalog.services.lineage_service import LineageService
from settings.portal import DwhCollectorSettings


class FakeMetadataProvider:
    def __init__(self, objects):
        self._objects = objects

    def list_assets(self):
        return self._objects

    def get_asset(self, qualified_name: str):
        return None


def _table():
    return CatalogObject(
        asset_type=AssetType.TABLE,
        database="dwh",
        schema="raw",
        name="ice_brent",
        native_id="123",
        columns=[],
    )


def _view():
    return CatalogObject(
        asset_type=AssetType.VIEW,
        database="dwh",
        schema="raw",
        name="v_ice_brent_latest",
        native_id="124",
        columns=[],
    )


def _catalog_objects():
    return [
        CatalogObject(asset_type=AssetType.DATABASE, database="dwh", schema=None, name="dwh"),
        CatalogObject(asset_type=AssetType.SCHEMA, database="dwh", schema="raw", name="raw"),
        _table(),
    ]


class _SqlProvider(FakeMetadataProvider):
    def list_relation_dependencies(self):
        return [
            RelationDependency(
                database="dwh",
                dependent_schema="raw",
                dependent_name="v_ice_brent_latest",
                source_schema="raw",
                source_name="ice_brent",
            )
        ]


class _MissingRegistry:
    def list_extraction_sources(self):
        raise ExtractionRegistryMissing("sys.data_extraction_sources is not present")

    def resolve_process_metadata(self, handler):
        raise AssertionError("should not be called")


def test_postgres_sql_adapter_links_view_to_table(store, now):
    objects = _catalog_objects() + [_view()]
    CatalogCollector(store, FakeMetadataProvider(objects)).run(now)
    run = PostgresSqlLineageAdapter(
        store,
        DwhCollectorSettings(),
        metadata_provider=_SqlProvider(objects),
    ).collect(now)
    assert run.status == CollectorStatus.SUCCESS
    assert run.details["edges"] == 1
    view = store.find_by_qualified_name("dwh.raw.v_ice_brent_latest")
    table = store.find_by_qualified_name("dwh.raw.ice_brent")
    assert view and table
    edges = store.list_relationships(asset_id=view.id, types={RelationshipType.DERIVED_FROM})
    assert len(edges) == 1
    assert edges[0].to_asset_id == table.id
    payload = LineageService(store).get_lineage(view.id)
    node_types = {node.asset_type for node in payload["nodes"]}
    assert node_types == {AssetType.VIEW, AssetType.TABLE}


def test_missing_extraction_registry_is_skipped_and_sql_lineage_remains(store, now):
    objects = _catalog_objects() + [_view()]
    result = run_daily_collection(
        store,
        metadata_provider=_SqlProvider(objects),
        lineage_provider=_MissingRegistry(),
        settings=DwhCollectorSettings(lineage_adapters="postgres_sql,extraction_registry"),
    )
    assert result["catalog"].status == CollectorStatus.SUCCESS
    assert result["extraction_registry"].status == CollectorStatus.SUCCESS
    assert result["extraction_registry"].details.get("skipped") is True
    assert result["extraction_registry"].details.get("reason") == "REGISTRY_ABSENT"
    assert result["postgres_sql"].status == CollectorStatus.SUCCESS
    assert result["postgres_sql"].details["edges"] == 1
    view = store.find_by_qualified_name("dwh.raw.v_ice_brent_latest")
    payload = LineageService(store).get_lineage(view.id)
    assert any(node.asset_type == AssetType.TABLE for node in payload["nodes"])
    assert not any(node.asset_type == AssetType.EXTRACTION_SOURCE for node in payload["nodes"])


def test_airflow_adapter_rebuilds_process_and_url_source(store, now, tmp_path):
    CatalogCollector(store, FakeMetadataProvider(_catalog_objects())).run(now)
    dag = tmp_path / "load_ice_brent.py"
    dag.write_text(
        """
from airflow import DAG

with DAG(dag_id="load_ice_brent", schedule=None):
    TARGET = "raw.ice_brent"
    URL = "https://user:token@api.example.com/v1/brent?api_key=secret"
    IGNORE = "https://airflow.apache.org/docs/"
""",
        encoding="utf-8",
    )
    run = AirflowDagsLineageAdapter(
        store, DwhCollectorSettings(airflow_dags_root=str(tmp_path))
    ).collect(now)
    assert run.status == CollectorStatus.SUCCESS
    assert run.details["writes"] == 1
    process = store.find_by_identity("airflow_dags", airflow_process_identity("load_ice_brent")[1])
    table = store.find_by_qualified_name("dwh.raw.ice_brent")
    assert process and table
    writes = [
        edge
        for edge in store.list_relationships(asset_id=process.id)
        if edge.relationship_type == RelationshipType.WRITES_TO
    ]
    assert writes[0].to_asset_id == table.id
    reads = [
        edge
        for edge in store.list_relationships(asset_id=process.id)
        if edge.relationship_type == RelationshipType.READS_FROM
    ]
    assert len(reads) == 1
    source = store.get_asset(reads[0].to_asset_id)
    assert source.asset_type == AssetType.DATA_SOURCE
    assert source.name == "https://api.example.com/v1/brent"
    assert "token" not in (source.attributes.get("url") or "")
    payload = LineageService(store).get_lineage(table.id)
    types = {node.asset_type for node in payload["nodes"]}
    assert types == {AssetType.TABLE, AssetType.PROCESS, AssetType.DATA_SOURCE}


def test_airflow_adapter_skips_when_root_missing(store, now):
    run = AirflowDagsLineageAdapter(
        store, DwhCollectorSettings(airflow_dags_root="")
    ).collect(now)
    assert run.status == CollectorStatus.SUCCESS
    assert run.details.get("skipped") is True


def test_normalize_url_strips_secrets_and_noise():
    assert normalize_url("https://user:token@api.example.com/v1/brent?api_key=secret") == (
        "https://api.example.com/v1/brent"
    )
    assert normalize_url("https://airflow.apache.org/docs/") is None
    assert url_data_source_identity("https://api.example.com/v1/brent")[0].startswith(
        "datasource:url:"
    )


def test_dynamic_plugin_and_unknown_spec_are_localized(store, now):
    good = load_lineage_adapters(
        store,
        DwhCollectorSettings(
            lineage_adapters="domains.catalog.lineage_adapters.postgres_sql:PostgresSqlLineageAdapter"
        ),
        metadata_provider=FakeMetadataProvider(_catalog_objects()),
    )
    assert good[0].name == "postgres_sql"
    bad = load_lineage_adapters(
        store, DwhCollectorSettings(lineage_adapters="missing.module:Nope")
    )
    run = bad[0].collect(now)
    assert run.status == CollectorStatus.FAILED
    assert run.details.get("code") == "ADAPTER_LOAD_FAILED"
    assert store.find_by_qualified_name("dwh.raw.ice_brent") is None
