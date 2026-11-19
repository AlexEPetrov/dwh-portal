import datetime
import uuid
from types import SimpleNamespace

from domains.catalog.collectors.catalog import CatalogCollector
from domains.catalog.collectors.changes import ChangeCollector
from domains.catalog.collectors.extraction_registry import ExtractionRegistryCollector
from domains.catalog.collectors.runner import run_daily_collection
from domains.catalog.collectors.storage import StorageCollector
from domains.catalog.identity import compute_structure_hash
from domains.catalog.models import (
    AssetColumn,
    AssetQuery,
    AssetStatus,
    AssetType,
    CollectorStatus,
)
from domains.catalog.providers.lineage import (
    ExtractionSourceRecord,
    LoaderMetadata,
    LoaderTarget,
)
from domains.catalog.providers.metadata import CatalogObject
from domains.catalog.providers.python_metadata import resolve_python_metadata
from domains.catalog.providers.rest_metadata import metadata_url
from settings.portal import DwhCollectorSettings, PortalSettings


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


def _schema(name: str) -> CatalogObject:
    return CatalogObject(asset_type=AssetType.SCHEMA, database="dwh", schema=name, name=name)


def _named_table(schema: str, name: str) -> CatalogObject:
    table = _table(name)
    return CatalogObject(
        asset_type=table.asset_type,
        database="dwh",
        schema=schema,
        name=name,
        description=table.description,
        native_id=f"{schema}.{name}",
        columns=table.columns,
        table_bytes=table.table_bytes,
        index_bytes=table.index_bytes,
        total_bytes=table.total_bytes,
        row_estimate=table.row_estimate,
    )


def test_catalog_scope_follows_the_full_schema_list(store, now):
    database = CatalogObject(asset_type=AssetType.DATABASE, database="dwh", schema=None, name="dwh")
    raw_only = [database, _schema("raw"), _named_table("raw", "ice_brent")]
    raw_and_core = raw_only + [_schema("core"), _named_table("core", "prices")]
    core_only = [database, _schema("core"), _named_table("core", "prices")]

    CatalogCollector(store, FakeMetadataProvider(raw_only)).run(now)
    CatalogCollector(store, FakeMetadataProvider(raw_and_core)).run(
        now + datetime.timedelta(hours=1)
    )
    active, _ = store.list_assets(AssetQuery(status=AssetStatus.ACTIVE, page_size=100))
    active_tables = {item.name for item in active if item.asset_type == AssetType.TABLE}
    assert active_tables == {"ice_brent", "prices"}

    CatalogCollector(store, FakeMetadataProvider(core_only)).run(now + datetime.timedelta(hours=2))
    active, _ = store.list_assets(AssetQuery(status=AssetStatus.ACTIVE, page_size=100))
    active_tables = {item.name for item in active if item.asset_type == AssetType.TABLE}
    deleted, _ = store.list_assets(AssetQuery(status=AssetStatus.DELETED, page_size=100))
    deleted_tables = {item.name for item in deleted if item.asset_type == AssetType.TABLE}
    assert active_tables == {"prices"}
    assert "ice_brent" in deleted_tables


def test_catalog_failure_does_not_soft_delete_existing_scope(store, now):
    class RaisingProvider:
        def list_assets(self):
            raise ValueError("schemas not found: missing")

    CatalogCollector(store, FakeMetadataProvider(_catalog_objects())).run(now)
    run = CatalogCollector(store, RaisingProvider()).run(now + datetime.timedelta(hours=1))
    assert run.status == CollectorStatus.FAILED
    assert "schemas not found: missing" in (run.message or "")
    active, _ = store.list_assets(AssetQuery(status=AssetStatus.ACTIVE, page_size=100))
    assert any(item.name == "ice_brent" for item in active)


def test_catalog_collector_is_idempotent(store, now):
    collector = CatalogCollector(store, FakeMetadataProvider(_catalog_objects()))
    collector.run(now)
    collector.run(now + datetime.timedelta(days=1))
    assets, _ = store.list_assets(AssetQuery(page_size=100))
    tables = [item for item in assets if item.asset_type == AssetType.TABLE]
    assert len(tables) == 1
    assert tables[0].first_seen_at == now


def test_python_handler_is_deferred_without_metadata_call(store, now):
    record = ExtractionSourceRecord(
        id="src-1",
        name="Brent",
        descr="doc",
        access_level=1,
        is_active=True,
        extract_source_type_id=1,
        extract_options={"subject_patterns": ["Brent"]},
        storage_options={"path": "landing/ice/brent", "password": "secret"},
        load_options={
            "handlers": [
                {
                    "handler_type": "Python",
                    "module": "missing.loader",
                    "entry_point": "SelectedLoader",
                    "options": {"password": "secret"},
                }
            ]
        },
        load_schedule_id=None,
        data_source_id="ice",
        data_source_name="ICE",
        tags=None,
        parent_id=None,
        comment=None,
    )

    class AssertNoResolve(FakeLineageProvider):
        def resolve_process_metadata(self, handler):
            raise AssertionError("Python handlers must not resolve get_metadata")

    ExtractionRegistryCollector(store, AssertNoResolve([record], {})).run(now)
    processes = [item for item in store.assets.values() if item.asset_type == AssetType.PROCESS]
    assert len(processes) == 1
    assert processes[0].attributes["metadata_status"] == "DEFERRED"
    assert processes[0].attributes["lineage_status"] == "UNRESOLVED"
    assert processes[0].attributes["module"] == "missing.loader"
    assert processes[0].attributes["entry_point"] == "SelectedLoader"
    assert "options" not in processes[0].attributes
    assert "password" not in processes[0].attributes
    storage = next(
        item for item in store.assets.values() if item.asset_type == AssetType.STORAGE_LOCATION
    )
    assert "password" not in storage.attributes
    assert not store.list_diagnostics(processes[0].id)


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
        load_options={
            "handlers": [{"handler_type": "RestApi", "url_path": "https://loader.internal/ok"}]
        },
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
        store, FakeLineageProvider([record], {"https://loader.internal/ok": metadata})
    ).run(now)
    assert run.status == CollectorStatus.PARTIAL
    unresolved = [item for item in store.assets.values() if item.attributes.get("unresolved")]
    assert unresolved
    assert unresolved[0].qualified_name.startswith("unresolved:")


def test_writes_to_table_and_storage_view_is_derived_from(store, now):
    CatalogCollector(store, FakeMetadataProvider(_catalog_objects())).run(now)
    view_obj = CatalogObject(
        asset_type=AssetType.VIEW,
        database="dwh",
        schema="raw",
        name="v_ice_brent_latest",
        native_id="124",
        columns=[],
    )
    CatalogCollector(store, FakeMetadataProvider(_catalog_objects() + [view_obj])).run(now)
    record = ExtractionSourceRecord(
        id="src-3",
        name="Brent",
        descr=None,
        access_level=None,
        is_active=True,
        extract_source_type_id=1,
        extract_options={},
        storage_options={"path": "landing/ice/brent"},
        load_options={
            "handlers": [
                {
                    "handler_type": "RestApi",
                    "name": "brent_rest",
                    "url_path": "https://loader.internal/ok",
                }
            ]
        },
        load_schedule_id=None,
        data_source_id="ice",
        data_source_name="ICE",
        tags=None,
        parent_id=None,
        comment=None,
    )
    base = LoaderTarget(type="table", database="dwh", schema="raw", name="ice_brent")
    metadata = LoaderMetadata(
        schema_version="1.0",
        name="ok.loader",
        writes_to=[
            base,
            LoaderTarget(type="s3", path="s3://bucket/ice/brent/"),
            LoaderTarget(
                type="view",
                database="dwh",
                schema="raw",
                name="v_ice_brent_latest",
                derived_from=base,
            ),
        ],
    )
    run = ExtractionRegistryCollector(
        store, FakeLineageProvider([record], {"https://loader.internal/ok": metadata})
    ).run(now)
    assert run.status == CollectorStatus.SUCCESS
    from domains.catalog.models import RelationshipType

    process = next(item for item in store.assets.values() if item.asset_type == AssetType.PROCESS)
    table = store.find_by_qualified_name("dwh.raw.ice_brent")
    view = store.find_by_qualified_name("dwh.raw.v_ice_brent_latest")
    assert table and view
    edges = store.list_relationships(asset_id=process.id)
    writes = [
        e
        for e in edges
        if e.relationship_type == RelationshipType.WRITES_TO and e.from_asset_id == process.id
    ]
    write_types = {store.get_asset(e.to_asset_id).asset_type for e in writes}
    assert write_types == {AssetType.TABLE, AssetType.STORAGE_LOCATION}
    derived = [
        e
        for e in store.list_relationships(asset_id=view.id)
        if e.relationship_type == RelationshipType.DERIVED_FROM
    ]
    assert len(derived) == 1
    assert derived[0].from_asset_id == view.id
    assert derived[0].to_asset_id == table.id


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
    types = {
        event.change_type.value for event in store.changes.values() if event.asset_id == table.id
    }
    assert "ADDED" in types
    assert "STRUCTURE_CHANGED" in types


def test_storage_run_keeps_the_catalog_snapshot(store, now):
    provider = FakeMetadataProvider(_catalog_objects())
    CatalogCollector(store, provider).run(now)
    storage_run = StorageCollector(store).run(now + datetime.timedelta(minutes=1))
    table = store.find_by_qualified_name("dwh.raw.ice_brent")
    assert table is not None
    snapshots = store.list_snapshots(asset_id=table.id)

    assert storage_run.status == CollectorStatus.SUCCESS
    assert storage_run.details["recorded_by"] == "catalog"
    assert len(snapshots) == 1
    assert snapshots[0].structure_hash
    assert snapshots[0].total_bytes == 110


def test_structure_change_survives_storage_run(store, now):
    provider = FakeMetadataProvider(_catalog_objects())
    CatalogCollector(store, provider).run(now)
    StorageCollector(store).run(now)
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
    StorageCollector(store).run(later)
    ChangeCollector(store).run(later)
    types = {
        event.change_type.value for event in store.changes.values() if event.asset_id == table.id
    }
    assert "STRUCTURE_CHANGED" in types


def test_change_detector_visits_every_asset_page(store, now):
    objects = [
        CatalogObject(asset_type=AssetType.DATABASE, database="dwh", schema=None, name="dwh"),
        _schema("raw"),
        _named_table("raw", "one"),
        _named_table("raw", "two"),
    ]
    CatalogCollector(store, FakeMetadataProvider(objects)).run(now)
    ChangeCollector(store, page_size=1).run(now)
    added_names = set()
    for event in store.changes.values():
        if event.change_type.value != "ADDED":
            continue
        asset = store.get_asset(event.asset_id)
        assert asset is not None
        added_names.add(asset.name)
    assert added_names == {"one", "two"}


def test_python_and_rest_discovery_helpers(monkeypatch):
    module = SimpleNamespace(
        get_metadata=lambda: {
            "schema_version": "1.0",
            "name": "ice_brent_loader",
            "writes_to": [
                {"type": "table", "database": "dwh", "schema": "raw", "name": "ice_brent"}
            ],
        }
    )

    def fake_import(name: str):
        if name == "company.ice_brent":
            return module
        raise ModuleNotFoundError(name)

    monkeypatch.setattr(
        "domains.catalog.providers.python_metadata.importlib.import_module", fake_import
    )
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
        settings=DwhCollectorSettings(lineage_adapters="postgres_sql,extraction_registry"),
    )
    assert result["catalog"].status == CollectorStatus.SUCCESS
    assert result["extraction_registry"].status == CollectorStatus.FAILED
    assert result["postgres_sql"].status == CollectorStatus.SUCCESS
    assert result["postgres_sql"].details.get("skipped") is True
    assert store.find_by_qualified_name("dwh.raw.ice_brent") is not None


def test_portal_store_purge_drops_previous_snapshots(store, now):
    CatalogCollector(store, FakeMetadataProvider(_catalog_objects())).run(now)
    assert not store.is_empty()
    store.purge()
    assert store.is_empty()
    assert store.relationships == {}
    assert store.runs == []


def test_collect_reset_purges_before_run(store, monkeypatch):
    from domains.catalog import collect as collect_mod

    CatalogCollector(store, FakeMetadataProvider(_catalog_objects())).run()
    assert not store.is_empty()
    monkeypatch.setattr(
        collect_mod,
        "get_portal_settings",
        lambda: PortalSettings(store="memory", seed_demo=False, reset_on_collect=False),
    )
    monkeypatch.setattr(collect_mod, "create_portal_store", lambda settings: store)
    monkeypatch.setattr(
        "domains.catalog.services.collection_service.run_daily_collection",
        lambda portal_store, **kwargs: {},
    )
    assert collect_mod.main([]) == 0
    assert not store.is_empty()
    assert collect_mod.main(["--reset"]) == 0
    assert store.is_empty()


def test_collect_reset_on_collect_setting(store, monkeypatch):
    from domains.catalog import collect as collect_mod

    CatalogCollector(store, FakeMetadataProvider(_catalog_objects())).run()
    monkeypatch.setattr(
        collect_mod,
        "get_portal_settings",
        lambda: PortalSettings(store="memory", seed_demo=False, reset_on_collect=True),
    )
    monkeypatch.setattr(collect_mod, "create_portal_store", lambda settings: store)
    monkeypatch.setattr(
        "domains.catalog.services.collection_service.run_daily_collection",
        lambda portal_store, **kwargs: {},
    )
    assert collect_mod.main([]) == 0
    assert store.is_empty()


def test_collect_cli_passes_airflow_lineage_mode(store, monkeypatch):
    from domains.catalog import collect as collect_mod

    captured = {}

    def fake_run(portal_store, **kwargs):
        captured["settings"] = kwargs.get("settings")
        return {}

    monkeypatch.setattr(
        collect_mod,
        "get_portal_settings",
        lambda: PortalSettings(store="memory", seed_demo=False),
    )
    monkeypatch.setattr(collect_mod, "create_portal_store", lambda settings: store)
    monkeypatch.setattr(
        "domains.catalog.services.collection_service.run_daily_collection",
        fake_run,
    )
    assert collect_mod.main(["--airflow-lineage-mode", "code"]) == 0
    assert captured["settings"].airflow_lineage_mode == "code"


def test_collect_cli_passes_growing_schema_list(store, monkeypatch):
    from domains.catalog import collect as collect_mod

    captured = {}

    def fake_run(portal_store, **kwargs):
        captured["schemas"] = kwargs.get("schemas")
        return {}

    monkeypatch.setattr(
        collect_mod,
        "get_portal_settings",
        lambda: PortalSettings(store="memory", seed_demo=False),
    )
    monkeypatch.setattr(collect_mod, "create_portal_store", lambda settings: store)
    monkeypatch.setattr(
        "domains.catalog.services.collection_service.run_daily_collection",
        fake_run,
    )
    assert collect_mod.main(["--schemas", "raw, core"]) == 0
    assert captured["schemas"] == ("raw", "core")
