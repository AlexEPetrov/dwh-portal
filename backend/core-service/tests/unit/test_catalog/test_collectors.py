import datetime
import uuid
from types import SimpleNamespace

from domains.catalog.collectors.catalog import CatalogCollector
from domains.catalog.collectors.changes import ChangeCollector
from domains.catalog.collectors.extraction_registry import ExtractionRegistryCollector
from domains.catalog.collectors.runner import run_daily_collection
from domains.catalog.identity import compute_structure_hash
from domains.catalog.models import AssetColumn, AssetQuery, AssetType, CollectorStatus
from domains.catalog.providers.lineage import (
    ExtractionSourceRecord,
    LoaderMetadata,
    LoaderTarget,
)
from domains.catalog.providers.metadata import CatalogObject
from domains.catalog.providers.python_metadata import resolve_python_metadata
from domains.catalog.providers.rest_metadata import metadata_url


class FakeMetadataProvider:
    def __init__(self, objects):
        self._objects = objects

    def list_assets(self):
        return self._objects

    def get_asset(self, qualified_name: str):
        return None


class FakeLineageProvider:
    def __init__(self, records, metadata_by_key):
        self._records = records
        self._metadata_by_key = metadata_by_key

    def list_extraction_sources(self):
        return self._records

    def resolve_process_metadata(self, handler):
        key = handler.get("module") or handler.get("url_path") or handler.get("handler_type")
        return self._metadata_by_key[key]


def _table(name="ice_brent"):
    return CatalogObject(
        asset_type=AssetType.TABLE,
        database="dwh",
        schema="raw",
        name=name,
        description="ICE Brent",
        native_id="123",
        columns=[
            {
                "ordinal": 1,
                "name": "trade_date",
                "data_type": "date",
                "nullable": False,
                "description": "Trading date",
            }
        ],
        table_bytes=100,
        index_bytes=10,
        total_bytes=110,
        row_estimate=5,
    )


def _catalog_objects():
    return [
        CatalogObject(asset_type=AssetType.DATABASE, database="dwh", schema=None, name="dwh"),
        CatalogObject(asset_type=AssetType.SCHEMA, database="dwh", schema="raw", name="raw"),
        _table(),
    ]


def test_catalog_collector_is_idempotent(store, now):
    collector = CatalogCollector(store, FakeMetadataProvider(_catalog_objects()))
    collector.run(now)
    collector.run(now + datetime.timedelta(days=1))
    assets, _ = store.list_assets(AssetQuery(page_size=100))
    tables = [item for item in assets if item.asset_type == AssetType.TABLE]
    assert len(tables) == 1
    assert tables[0].first_seen_at == now


def test_missing_python_metadata_is_localized(store, now):
    record = ExtractionSourceRecord(
        id="src-1",
        name="Brent",
        descr="doc",
        access_level=1,
        is_active=True,
        extract_source_type_id=1,
        extract_options={"subject_patterns": ["Brent"]},
        storage_options={"path": "landing/ice/brent", "password": "secret"},
        load_options={"handlers": [{"handler_type": "Python", "module": "missing.loader"}]},
        load_schedule_id=None,
        data_source_id="ice",
        data_source_name="ICE",
        tags=None,
        parent_id=None,
        comment=None,
    )
    metadata = LoaderMetadata(
        schema_version="1.0",
        name="missing.loader",
        metadata_status="MISSING",
        diagnostic={"code": "METADATA_MISSING", "message": "get_metadata() is not implemented"},
    )
    ExtractionRegistryCollector(
        store, FakeLineageProvider([record], {"missing.loader": metadata})
    ).run(now)
    processes = [item for item in store.assets.values() if item.asset_type == AssetType.PROCESS]
    assert len(processes) == 1
    assert processes[0].attributes["metadata_status"] == "MISSING"
    assert processes[0].attributes["lineage_status"] == "UNRESOLVED"
    storage = next(item for item in store.assets.values() if item.asset_type == AssetType.STORAGE_LOCATION)
    assert "password" not in storage.attributes
    assert store.list_diagnostics(processes[0].id)


def test_unresolved_target_is_kept_and_does_not_fail_run(store, now):
    record = ExtractionSourceRecord(
        id="src-2",
        name="Brent",
        descr=None,
        access_level=None,
        is_active=True,
        extract_source_type_id=1,
        extract_options={},
        storage_options={"path": "landing/ice/brent"},
        load_options={"handlers": [{"handler_type": "Python", "module": "ok.loader"}]},
        load_schedule_id=None,
        data_source_id="ice",
        data_source_name="ICE",
        tags=None,
        parent_id=None,
        comment=None,
    )
    metadata = LoaderMetadata(
        schema_version="1.0",
        name="ok.loader",
        writes_to=[LoaderTarget(type="table", database="dwh", schema="raw", name="missing_table")],
    )
    run = ExtractionRegistryCollector(
        store, FakeLineageProvider([record], {"ok.loader": metadata})
    ).run(now)
    assert run.status == CollectorStatus.PARTIAL
    unresolved = [item for item in store.assets.values() if item.attributes.get("unresolved")]
    assert unresolved
    assert unresolved[0].qualified_name.startswith("unresolved:")


def test_change_detector_emits_added_and_structure_change(store, now):
    CatalogCollector(store, FakeMetadataProvider(_catalog_objects())).run(now)
    ChangeCollector(store).run(now)
    table = store.find_by_qualified_name("dwh.raw.ice_brent")
    assert table is not None
    columns = store.get_columns(table.id)
    later = now + datetime.timedelta(days=1)
    extra = columns + [
        AssetColumn(
            asset_id=table.id,
            ordinal=2,
            name="currency",
            data_type="varchar(3)",
            nullable=True,
        )
    ]
    store.replace_columns(table.id, extra)
    latest = store.latest_snapshot(table.id)
    store.add_snapshot(
        latest.model_copy(
            update={
                "id": uuid.uuid4(),
                "snapshot_at": later,
                "structure_hash": compute_structure_hash(AssetType.TABLE, extra),
            }
        )
    )
    ChangeCollector(store).run(later)
    types = {event.change_type.value for event in store.changes.values() if event.asset_id == table.id}
    assert "ADDED" in types
    assert "STRUCTURE_CHANGED" in types


def test_python_and_rest_discovery_helpers(monkeypatch):
    module = SimpleNamespace(
        get_metadata=lambda: {
            "schema_version": "1.0",
            "name": "ice_brent_loader",
            "writes_to": [{"type": "table", "database": "dwh", "schema": "raw", "name": "ice_brent"}],
        }
    )

    def fake_import(name: str):
        if name == "company.ice_brent":
            return module
        raise ModuleNotFoundError(name)

    monkeypatch.setattr("domains.catalog.providers.python_metadata.importlib.import_module", fake_import)
    resolved = resolve_python_metadata("company.ice_brent", "ice")
    assert resolved.writes_to[0].name == "ice_brent"
    missing = resolve_python_metadata("missing.mod", "ice")
    assert missing.metadata_status == "FAILED"
    assert metadata_url("https://loader.internal/api/v1/ice/brent") == (
        "https://loader.internal/api/v1/ice/brent/metadata"
    )


def test_daily_runner_localizes_lineage_failure(store):
    class BrokenLineage:
        def list_extraction_sources(self):
            raise RuntimeError("registry unavailable")

        def resolve_process_metadata(self, handler):
            raise AssertionError("should not be called")

    result = run_daily_collection(
        store,
        metadata_provider=FakeMetadataProvider(_catalog_objects()),
        lineage_provider=BrokenLineage(),
    )
    assert result["catalog"].status == CollectorStatus.SUCCESS
    assert result["extraction_registry"].status == CollectorStatus.FAILED
    assert store.find_by_qualified_name("dwh.raw.ice_brent") is not None
