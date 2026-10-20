import logging
import warnings

from domains.catalog.collectors.catalog import CatalogCollector
from domains.catalog.collectors.runner import run_daily_collection
from domains.catalog.identity import airflow_extraction_identity, airflow_process_identity
from domains.catalog.collectors.extraction_registry import ExtractionRegistryCollector
from domains.catalog.lineage_adapters.airflow_dags import (
    AirflowDagsLineageAdapter,
    parse_dag_meta,
)
from domains.catalog.lineage_adapters.airflow_syntax import parse_module, write_targets_for_closure
from domains.catalog.lineage_adapters.postgres_sql import PostgresSqlLineageAdapter
from domains.catalog.lineage_adapters.python_modules import PythonModulesLineageAdapter
from domains.catalog.lineage_adapters.registry import default_adapter_specs, load_lineage_adapters
from domains.catalog.models import AssetType, CollectorStatus, RelationshipType
from domains.catalog.providers.extraction_registry import ExtractionRegistryMissing
from domains.catalog.providers.lineage import ExtractionSourceRecord
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


def test_airflow_adapter_uses_module_name_and_dag_description(store, now, tmp_path):
    CatalogCollector(store, FakeMetadataProvider(_catalog_objects())).run(now)
    dag = tmp_path / "load_platts_egd.py"
    dag.write_text(
        '''
from airflow import DAG

default_args = {}
doc_md = "docs"

dag = DAG(
    dag_id='load_platts_egd',
    default_args=default_args,
    schedule_interval="10 * * * *",
    render_template_as_native_obj=True,
    tags=["platts_egd", "egd"],
    catchup=False,
    max_active_runs=1,
    concurrency=1,
    description="Загрузка данных  Platts European Gas Daily",
    doc_md=doc_md
)

def load_data():
    year_dates.to_sql(schema="raw", name="ice_brent", con=conn, if_exists="append")
''',
        encoding="utf-8",
    )
    run = AirflowDagsLineageAdapter(
        store, DwhCollectorSettings(airflow_dags_root=str(tmp_path))
    ).collect(now)
    assert run.status == CollectorStatus.SUCCESS
    process = store.find_by_identity("airflow_dags", airflow_process_identity("load_platts_egd")[1])
    table = store.find_by_qualified_name("dwh.raw.ice_brent")
    assert process and table
    assert process.name == "load_platts_egd"
    assert process.attributes.get("source_files") == ["load_platts_egd.py"]
    writes = [
        edge
        for edge in store.list_relationships(asset_id=process.id)
        if edge.relationship_type == RelationshipType.WRITES_TO
    ]
    assert writes[0].to_asset_id == table.id
    extraction = store.find_by_identity(
        "airflow_dags", airflow_extraction_identity("load_platts_egd")[1]
    )
    assert extraction is not None
    assert extraction.asset_type == AssetType.EXTRACTION_SOURCE
    assert extraction.description == "Загрузка данных Platts European Gas Daily"
    assert not any(item.asset_type == AssetType.DATA_SOURCE for item in store.assets.values())
    assert not any(item.asset_type == AssetType.STORAGE_LOCATION for item in store.assets.values())
    payload = LineageService(store).get_lineage(table.id)
    types = {node.asset_type for node in payload["nodes"]}
    assert types == {AssetType.TABLE, AssetType.PROCESS, AssetType.EXTRACTION_SOURCE}


def test_airflow_adapter_does_not_create_storage_location(store, now, tmp_path):
    CatalogCollector(store, FakeMetadataProvider(_catalog_objects())).run(now)
    folder = tmp_path / "platts_egd"
    folder.mkdir()
    (folder / "load_platts_egd.py").write_text(
        '''
from airflow import DAG

dag = DAG(
    dag_id="load_platts_egd",
    description="Загрузка Platts",
)

def load_data():
    year_dates.to_sql(schema="raw", name="ice_brent", con=conn, if_exists="append")
''',
        encoding="utf-8",
    )
    (folder / "paths.py").write_text(
        'LANDING = "/data/landing/platts/egd"\n',
        encoding="utf-8",
    )
    run = AirflowDagsLineageAdapter(
        store, DwhCollectorSettings(airflow_dags_root=str(tmp_path))
    ).collect(now)
    assert run.status == CollectorStatus.SUCCESS
    process = store.find_by_identity(
        "airflow_dags", airflow_process_identity("platts_egd/load_platts_egd")[1]
    )
    assert process is not None
    assert not any(
        edge.relationship_type == RelationshipType.READS_FROM
        for edge in store.list_relationships(asset_id=process.id)
    )
    assert not any(item.asset_type == AssetType.STORAGE_LOCATION for item in store.assets.values())
    extraction = store.find_by_identity(
        "airflow_dags", airflow_extraction_identity("load_platts_egd")[1]
    )
    table = store.find_by_qualified_name("dwh.raw.ice_brent")
    assert extraction and table
    extracts = store.list_relationships(asset_id=extraction.id, types={RelationshipType.EXTRACTS_TO})
    writes = store.list_relationships(asset_id=process.id, types={RelationshipType.WRITES_TO})
    assert extracts[0].to_asset_id == process.id
    assert writes[0].to_asset_id == table.id


def test_airflow_and_sql_form_extraction_to_view_chain(store, now, tmp_path):
    objects = _catalog_objects() + [_view()]
    CatalogCollector(store, FakeMetadataProvider(objects)).run(now)
    PostgresSqlLineageAdapter(
        store,
        DwhCollectorSettings(),
        metadata_provider=_SqlProvider(objects),
    ).collect(now)
    dag = tmp_path / "load_platts_egd.py"
    dag.write_text(
        '''
from airflow import DAG

dag = DAG(dag_id="load_platts_egd", description="Загрузка Platts")

def load_data():
    year_dates.to_sql(schema="raw", name="ice_brent", con=conn, if_exists="append")
''',
        encoding="utf-8",
    )
    AirflowDagsLineageAdapter(
        store, DwhCollectorSettings(airflow_dags_root=str(tmp_path))
    ).collect(now)
    view = store.find_by_qualified_name("dwh.raw.v_ice_brent_latest")
    payload = LineageService(store).get_lineage(view.id)
    types = {node.asset_type for node in payload["nodes"]}
    assert types == {
        AssetType.VIEW,
        AssetType.TABLE,
        AssetType.PROCESS,
        AssetType.EXTRACTION_SOURCE,
    }
    assert AssetType.STORAGE_LOCATION not in types
    assert AssetType.DATA_SOURCE not in types


def test_airflow_adapter_follows_imports_and_requires_write(store, now, tmp_path):
    CatalogCollector(store, FakeMetadataProvider(_catalog_objects())).run(now)
    pkg = tmp_path / "platts_egd"
    scrapers = pkg / "scrapers"
    scrapers.mkdir(parents=True)
    (scrapers / "fetch.py").write_text(
        '''
URL = "https://gnpholding.gazprom.ru/calculation-data"

def get_online_data():
    return requests.get(URL).text
''',
        encoding="utf-8",
    )
    (pkg / "db_models.py").write_text(
        '''
from sqlalchemy.dialects.postgresql import insert

PLATTS_SCHEMA = "raw"
PLATTS_TABLE_NAME = "ice_brent"

class EuropeanGasDaily:
    __tablename__ = PLATTS_TABLE_NAME
    __table_args__ = {"schema": PLATTS_SCHEMA}

def upsert(session, model, rows):
    table = model.__table__
    stmt = insert(table)
    on_conflict_stmt = stmt.on_conflict_do_update(set_={})
    session.execute(on_conflict_stmt)
''',
        encoding="utf-8",
    )
    (pkg / "dag_platts_etl.py").write_text(
        '''
from airflow import DAG
from dags.platts_egd.scrapers.fetch import get_online_data
from dags.platts_egd.db_models import EuropeanGasDaily, upsert

def load_data():
    data = get_online_data()
    upsert(session, EuropeanGasDaily, data)

dag = DAG(
    dag_id="load_platts_egd",
    description="Загрузка Platts",
)
''',
        encoding="utf-8",
    )
    (pkg / "paths.py").write_text('LANDING = "/data/landing/platts/egd"\n', encoding="utf-8")
    run = AirflowDagsLineageAdapter(
        store, DwhCollectorSettings(airflow_dags_root=str(tmp_path))
    ).collect(now)
    assert run.status == CollectorStatus.SUCCESS
    process = store.find_by_identity(
        "airflow_dags", airflow_process_identity("platts_egd/dag_platts_etl")[1]
    )
    table = store.find_by_qualified_name("dwh.raw.ice_brent")
    assert process and table
    writes = store.list_relationships(asset_id=process.id, types={RelationshipType.WRITES_TO})
    assert writes[0].to_asset_id == table.id
    assert not any(item.asset_type == AssetType.DATA_SOURCE for item in store.assets.values())
    assert not any(item.asset_type == AssetType.STORAGE_LOCATION for item in store.assets.values())


def test_airflow_adapter_ignores_select_without_write(store, now, tmp_path):
    CatalogCollector(store, FakeMetadataProvider(_catalog_objects())).run(now)
    (tmp_path / "plot_dag.py").write_text(
        '''
from airflow import DAG

dag = DAG(dag_id="rates_plots", description="График")
SQL = "SELECT * FROM raw.ice_brent"
''',
        encoding="utf-8",
    )
    run = AirflowDagsLineageAdapter(
        store, DwhCollectorSettings(airflow_dags_root=str(tmp_path))
    ).collect(now)
    assert run.status == CollectorStatus.SUCCESS
    assert run.details.get("writes", 0) == 0
    assert store.find_by_identity("airflow_dags", airflow_process_identity("plot_dag")[1]) is None


def test_airflow_adapter_skips_when_root_missing(store, now):
    run = AirflowDagsLineageAdapter(
        store, DwhCollectorSettings(airflow_dags_root="")
    ).collect(now)
    assert run.status == CollectorStatus.SUCCESS
    assert run.details.get("skipped") is True


def test_default_adapters_include_python_modules():
    assert default_adapter_specs(DwhCollectorSettings()) == [
        "postgres_sql",
        "extraction_registry",
        "python_modules",
        "airflow_dags",
    ]


def test_python_modules_skips_when_root_missing(store, now):
    run = PythonModulesLineageAdapter(
        store, DwhCollectorSettings(python_modules_root="")
    ).collect(now)
    assert run.status == CollectorStatus.SUCCESS
    assert run.details.get("skipped") is True
    assert run.details.get("reason") == "MODULES_ROOT_MISSING"


class _NoResolveRegistry:
    def __init__(self, records):
        self._records = records

    def list_extraction_sources(self):
        return self._records

    def resolve_process_metadata(self, handler):
        raise AssertionError("must not resolve Python metadata")


def _python_source_record(module: str = "loaders.ice_brent", source_id: str = "src-py-1"):
    return ExtractionSourceRecord(
        id=source_id,
        name="Brent",
        descr=None,
        access_level=None,
        is_active=True,
        extract_source_type_id=1,
        extract_options={},
        storage_options={"path": "landing/ice/brent"},
        load_options={"handlers": [{"handler_type": "Python", "module": module}]},
        load_schedule_id=None,
        data_source_id="ice",
        data_source_name="ICE",
        tags=None,
        parent_id=None,
        comment=None,
    )


def test_python_modules_logs_module_lookup(store, now, tmp_path, caplog):
    CatalogCollector(store, FakeMetadataProvider(_catalog_objects())).run(now)
    package = tmp_path / "loaders"
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "ice_brent.py").write_text(
        '''
def load_data(conn):
    year_dates.to_sql(schema="raw", name="ice_brent", con=conn, if_exists="append")
''',
        encoding="utf-8",
    )
    ExtractionRegistryCollector(
        store,
        _NoResolveRegistry(
            [
                _python_source_record(),
                _python_source_record("loaders.missing_one", "src-py-2"),
            ]
        ),
    ).run(now)
    with caplog.at_level(logging.INFO):
        PythonModulesLineageAdapter(
            store, DwhCollectorSettings(python_modules_root=str(tmp_path))
        ).collect(now)
    text = caplog.text
    assert f"ищем модули в {tmp_path}" in text
    assert "модуль loaders.ice_brent" in text
    assert "schema/table: raw.ice_brent" in text
    assert "в каталоге: raw.ice_brent" in text
    assert "модуль loaders.missing_one" in text
    assert f"ищем в {tmp_path / 'loaders' / 'missing_one.py'} — не найден" in text


def test_python_modules_attaches_writes_to_registry_process(store, now, tmp_path):
    CatalogCollector(store, FakeMetadataProvider(_catalog_objects())).run(now)
    package = tmp_path / "loaders"
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "ice_brent.py").write_text(
        '''
def load_data(conn):
    year_dates.to_sql(schema="raw", name="ice_brent", con=conn, if_exists="append")
''',
        encoding="utf-8",
    )
    ExtractionRegistryCollector(store, _NoResolveRegistry([_python_source_record()])).run(now)
    process = next(item for item in store.assets.values() if item.asset_type == AssetType.PROCESS)
    assert process.attributes["metadata_status"] == "DEFERRED"
    process_id = process.id

    run = PythonModulesLineageAdapter(
        store,
        DwhCollectorSettings(
            python_modules_root=str(tmp_path),
            python_modules_lineage_mode="catalog",
        ),
    ).collect(now)
    assert run.status == CollectorStatus.SUCCESS
    assert run.details["writes"] == 1
    assert run.details["resolved"] == 1

    process = store.get_asset(process_id)
    assert process.attributes["metadata_status"] == "OK"
    assert process.attributes["lineage_status"] == "RESOLVED"
    table = store.find_by_qualified_name("dwh.raw.ice_brent")
    writes = [
        edge
        for edge in store.list_relationships(asset_id=process.id)
        if edge.relationship_type == RelationshipType.WRITES_TO
    ]
    assert len(writes) == 1
    assert writes[0].to_asset_id == table.id
    # Must enrich the registry PROCESS, not create an Airflow-style duplicate.
    processes = [item for item in store.assets.values() if item.asset_type == AssetType.PROCESS]
    assert len(processes) == 1


def test_python_modules_does_not_use_airflow_dags_root(store, now, tmp_path):
    CatalogCollector(store, FakeMetadataProvider(_catalog_objects())).run(now)
    dags = tmp_path / "dags"
    modules = tmp_path / "modules"
    dags.mkdir()
    modules.mkdir()
    package = modules / "loaders"
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "ice_brent.py").write_text(
        '''
def load_data(conn):
    year_dates.to_sql(schema="raw", name="ice_brent", con=conn, if_exists="append")
''',
        encoding="utf-8",
    )
    (dags / "ignored.py").write_text(
        '''
from airflow import DAG
dag = DAG(dag_id="ignored")
def load_data(conn):
    year_dates.to_sql(schema="raw", name="ice_brent", con=conn, if_exists="append")
''',
        encoding="utf-8",
    )
    ExtractionRegistryCollector(store, _NoResolveRegistry([_python_source_record()])).run(now)
    # Only Airflow root set — python_modules must skip, not scan DAGs.
    skipped = PythonModulesLineageAdapter(
        store, DwhCollectorSettings(airflow_dags_root=str(dags), python_modules_root="")
    ).collect(now)
    assert skipped.details.get("skipped") is True
    process = next(item for item in store.assets.values() if item.asset_type == AssetType.PROCESS)
    assert process.attributes["metadata_status"] == "DEFERRED"

    run = PythonModulesLineageAdapter(
        store, DwhCollectorSettings(python_modules_root=str(modules))
    ).collect(now)
    assert run.details["writes"] == 1


def test_airflow_catalog_mode_skips_table_absent_from_snapshot(store, now, tmp_path):
    CatalogCollector(store, FakeMetadataProvider(_catalog_objects())).run(now)
    (tmp_path / "load_gassco.py").write_text(
        '''
from airflow import DAG

dag = DAG(dag_id="load_gassco", description="Gassco")

def load_data():
    sql = "INSERT INTO src_gassco.gassco_flows VALUES (1)"
''',
        encoding="utf-8",
    )
    run = AirflowDagsLineageAdapter(
        store,
        DwhCollectorSettings(airflow_dags_root=str(tmp_path), airflow_lineage_mode="catalog"),
    ).collect(now)
    assert run.status == CollectorStatus.SUCCESS
    assert run.details.get("mode") == "catalog"
    assert run.details.get("writes", 0) == 0
    assert store.find_by_identity("airflow_dags", airflow_process_identity("load_gassco")[1]) is None


def test_airflow_code_mode_materializes_unresolved_write_target(store, now, tmp_path):
    (tmp_path / "load_gassco.py").write_text(
        '''
from airflow import DAG

CBR_SCHEMA = "src_gassco"
CBR_TABLE = "gassco_flows"

dag = DAG(dag_id="load_gassco", description="Gassco")

def load_data():
    sql = f"INSERT INTO {CBR_SCHEMA}.{CBR_TABLE} VALUES (1)"
''',
        encoding="utf-8",
    )
    run = AirflowDagsLineageAdapter(
        store,
        DwhCollectorSettings(airflow_dags_root=str(tmp_path), airflow_lineage_mode="code"),
    ).collect(now)
    assert run.status == CollectorStatus.SUCCESS
    assert run.details.get("mode") == "code"
    assert run.details.get("writes", 0) == 1
    assert run.details.get("unresolved", 0) == 1
    process = store.find_by_identity("airflow_dags", airflow_process_identity("load_gassco")[1])
    assert process is not None
    writes = store.list_relationships(asset_id=process.id, types={RelationshipType.WRITES_TO})
    table = store.get_asset(writes[0].to_asset_id)
    assert table is not None
    assert table.attributes.get("unresolved") is True
    assert table.attributes["target_ref"]["schema"] == "src_gassco"
    assert table.attributes["target_ref"]["name"] == "gassco_flows"
    assert process.attributes.get("source_files") == ["load_gassco.py"]
    assert table.attributes.get("source_files") == ["load_gassco.py"]


def test_airflow_code_mode_reads_insert_fstring_with_unresolved_columns(store, now, tmp_path):
    (tmp_path / "load_rgmc.py").write_text(
        '''
from airflow import DAG

SCHEMA, TABLE = "src_rgmc", "an_p_15"
TABLE_FIELDS = ["latitude", "longitude"]

dag = DAG(dag_id="load_rgmc", description="RGMC")

def load_file():
    fields = ", ".join(TABLE_FIELDS)
    fields_subst = ", ".join([f":{field}" for field in TABLE_FIELDS])
    sql = text(f"INSERT INTO {SCHEMA}.{TABLE} ({fields}) VALUES ({fields_subst})")
    return sql
''',
        encoding="utf-8",
    )
    run = AirflowDagsLineageAdapter(
        store,
        DwhCollectorSettings(airflow_dags_root=str(tmp_path), airflow_lineage_mode="code"),
    ).collect(now)
    assert run.status == CollectorStatus.SUCCESS
    assert run.details.get("writes", 0) == 1
    process = store.find_by_identity("airflow_dags", airflow_process_identity("load_rgmc")[1])
    assert process is not None
    writes = store.list_relationships(asset_id=process.id, types={RelationshipType.WRITES_TO})
    table = store.get_asset(writes[0].to_asset_id)
    assert table is not None
    assert table.attributes["target_ref"]["schema"] == "src_rgmc"
    assert table.attributes["target_ref"]["name"] == "an_p_15"


def _targets(path, source: str):
    facts = parse_module(path, source)
    assert facts is not None
    return write_targets_for_closure([path], {path: facts})


def test_loader_attribute_pipe_reads_string_table_on_subclass(tmp_path):
    path = tmp_path / "epias.py"
    source = '''
class EpiasBaseLoader:
    _TABLE_NAME = None
    _DB_SCHEMA = None

    @classmethod
    def load_file(cls, df):
        cls.save_to_db(df, table_name=cls._TABLE_NAME, schema=cls._DB_SCHEMA)

    @classmethod
    def save_to_db(cls, df, table_name=None, schema=None):
        df.to_sql(table_name, con=get_engine(), schema=schema, if_exists="append", index=False)

class EpiasGdrpLoader(EpiasBaseLoader):
    _DB_SCHEMA = "src_epias"
    _TABLE_NAME = "gas_daily_reference_prices"

class EpiasTdaaLoader(EpiasBaseLoader):
    _DB_SCHEMA = "src_epias"
    _TABLE_NAME = "gas_transmission_daily_actualization_amount"
'''
    refs = _targets(path, source)
    assert [(item.schema, item.name) for item in refs] == [
        ("src_epias", "gas_daily_reference_prices"),
        ("src_epias", "gas_transmission_daily_actualization_amount"),
    ]


def test_loader_attribute_pipe_inherits_schema_and_follows_orm_name(tmp_path):
    path = tmp_path / "loader.py"
    source = '''
INBOX_SCHEMA = "src_inbox"

class InboxModel:
    __tablename__ = "bids"
    __table_args__ = {"schema": "src_orm"}

class BaseLoader:
    _DB_SCHEMA = INBOX_SCHEMA

    def save(self, df, table_name=None, schema=None):
        df.to_sql(table_name, schema=schema)

class ConstLoader(BaseLoader):
    _TABLE_NAME = "acts"

class OrmLoader(BaseLoader):
    _MODEL = InboxModel
    _TABLE_NAME = _MODEL.__tablename__
    _DB_SCHEMA = InboxModel.__table_args__["schema"]
'''
    refs = _targets(path, source)
    assert [(item.schema, item.name) for item in refs] == [
        ("src_inbox", "acts"),
        ("src_orm", "bids"),
    ]


def test_class_attribute_in_write_slot_resolves_to_table(tmp_path):
    path = tmp_path / "mrg.py"
    source = '''
class OtherLoader:
    SCHEMA, TABLE = "src_other", "other_table"

    def load(self, df):
        df.to_sql(name=self.TABLE, schema=self.SCHEMA, if_exists="append", index=False)

class MrgDemandsForecastLoader:
    SCHEMA, TABLE = "src_d314", "mrg_demands_forecast"
    CHUNK_SIZE = 1000

    def load(self, df):
        df.to_sql(
            name=cls.TABLE, con=get_engine(), schema=cls.SCHEMA,
            if_exists="append", index=False, method="multi", chunksize=cls.CHUNK_SIZE,
        )
'''
    refs = _targets(path, source)
    assert [(item.schema, item.name) for item in refs] == [
        ("src_other", "other_table"),
        ("src_d314", "mrg_demands_forecast"),
    ]


def test_sql_fstring_resolves_class_attributes(tmp_path):
    path = tmp_path / "mrg.py"
    source = '''
class MrgDemandsForecastLoader:
    SCHEMA, TABLE = "src_d314", "mrg_demands_forecast"

    def load(self, fields, values):
        sql = f"INSERT INTO {cls.SCHEMA}.{cls.TABLE} ({fields}) VALUES ({values})"
        conn.execute(text(sql))
'''
    refs = _targets(path, source)
    assert [(item.schema, item.name) for item in refs] == [
        ("src_d314", "mrg_demands_forecast"),
    ]


def test_tables_schema_pipe_reads_dict_keys(tmp_path):
    path = tmp_path / "export_scenarios.py"
    source = '''
EXPORT_SCENARIOS_SCHEMA = "sol_export_scnr"
EXPORT_SCENARIOS_INFO = "export_scenarios_info"
EXPORT_SCENARIOS_INFO_UNQ = "sol_export_scnr_export_scenarios_info_unq"
EXPORT_SCENARIOS = "export_scenarios"
EXPORT_SCENARIOS_UNQ = "sol_export_scnr_export_scenarios_unq"

class ExportScenariosLoader(BaseExcelTemplateFileModel):
    _DB_SCHEMA = EXPORT_SCENARIOS_SCHEMA
    _TABLES_SCHEMA = {
        EXPORT_SCENARIOS_INFO: {"data": None, "unique_key": EXPORT_SCENARIOS_INFO_UNQ},
        EXPORT_SCENARIOS: {"data": None, "unique_key": EXPORT_SCENARIOS_UNQ},
    }

    @classmethod
    def save_db_schema(cls, schema):
        for table_name, table in schema.items():
            sql = f"""INSERT INTO {cls._DB_SCHEMA}.{table_name} ({fields})
                      VALUES ({values}) ON CONFLICT ON CONSTRAINT {unique_constraint}
                      DO UPDATE SET ({fields}) = ({update_fields})"""
            conn.execute(text(sql), row)
'''
    refs = _targets(path, source)
    assert [(item.schema, item.name) for item in refs] == [
        ("sol_export_scnr", "export_scenarios_info"),
        ("sol_export_scnr", "export_scenarios"),
    ]


def test_sql_pipe_wins_over_loader_attributes(tmp_path):
    path = tmp_path / "loader.py"
    source = '''
SCHEMA, TABLE = "src_rgmc", "an_p_15"

class Loader:
    _DB_SCHEMA = "src_other"
    _TABLE_NAME = "other"

    def load(self):
        sql = f"INSERT INTO {SCHEMA}.{TABLE} ({fields}) VALUES ({vals})"
'''
    refs = _targets(path, source)
    assert [(item.schema, item.name) for item in refs] == [("src_rgmc", "an_p_15")]


def test_airflow_code_mode_skips_insert_fstring_without_constant_table(store, now, tmp_path):
    (tmp_path / "load_rgmc.py").write_text(
        '''
from airflow import DAG

dag = DAG(dag_id="load_rgmc", description="RGMC")

def load_file(schema, table, fields):
    sql = text(f"INSERT INTO {schema}.{table} ({fields}) VALUES (:x)")
    return sql
''',
        encoding="utf-8",
    )
    run = AirflowDagsLineageAdapter(
        store,
        DwhCollectorSettings(airflow_dags_root=str(tmp_path), airflow_lineage_mode="code"),
    ).collect(now)
    assert run.status == CollectorStatus.SUCCESS
    assert run.details.get("writes", 0) == 0
    assert store.find_by_identity("airflow_dags", airflow_process_identity("load_rgmc")[1]) is None


def test_airflow_code_mode_storage_records_imported_source_file(store, now, tmp_path):
    pkg = tmp_path / "platts_egd"
    pkg.mkdir()
    (pkg / "paths.py").write_text(
        'LANDING = "/data/landing/platts/egd"\n',
        encoding="utf-8",
    )
    (pkg / "load_platts_egd.py").write_text(
        '''
from airflow import DAG
from dags.platts_egd.paths import LANDING

dag = DAG(dag_id="load_platts_egd", description="Загрузка Platts")

def load_data():
    sql = "INSERT INTO src_gassco.gassco_flows VALUES (1)"
    return LANDING
''',
        encoding="utf-8",
    )
    run = AirflowDagsLineageAdapter(
        store,
        DwhCollectorSettings(airflow_dags_root=str(tmp_path), airflow_lineage_mode="code"),
    ).collect(now)
    assert run.status == CollectorStatus.SUCCESS
    assert run.details.get("storages", 0) == 1
    process = store.find_by_identity(
        "airflow_dags", airflow_process_identity("platts_egd/load_platts_egd")[1]
    )
    storage = store.find_by_qualified_name("storage:/data/landing/platts/egd")
    assert process and storage
    assert storage.asset_type == AssetType.STORAGE_LOCATION
    assert storage.attributes.get("source_files") == ["platts_egd/paths.py"]
    reads = store.list_relationships(asset_id=process.id, types={RelationshipType.READS_FROM})
    assert reads[0].to_asset_id == storage.id
    extraction = store.find_by_identity(
        "airflow_dags", airflow_extraction_identity("load_platts_egd")[1]
    )
    assert extraction is not None
    extracts = store.list_relationships(
        asset_id=extraction.id, types={RelationshipType.EXTRACTS_TO}
    )
    assert {edge.to_asset_id for edge in extracts} >= {process.id, storage.id}


def test_airflow_code_mode_ignores_unimported_paths_file(store, now, tmp_path):
    CatalogCollector(store, FakeMetadataProvider(_catalog_objects())).run(now)
    folder = tmp_path / "platts_egd"
    folder.mkdir()
    (folder / "load_platts_egd.py").write_text(
        '''
from airflow import DAG

dag = DAG(dag_id="load_platts_egd", description="Загрузка Platts")

def load_data():
    year_dates.to_sql(schema="raw", name="ice_brent", con=conn, if_exists="append")
''',
        encoding="utf-8",
    )
    (folder / "paths.py").write_text(
        'LANDING = "/data/landing/platts/egd"\n',
        encoding="utf-8",
    )
    run = AirflowDagsLineageAdapter(
        store,
        DwhCollectorSettings(airflow_dags_root=str(tmp_path), airflow_lineage_mode="code"),
    ).collect(now)
    assert run.status == CollectorStatus.SUCCESS
    assert run.details.get("storages", 0) == 0
    assert store.find_by_qualified_name("storage:/data/landing/platts/egd") is None


def test_airflow_code_mode_ignores_main_block_paths_and_writes(store, now, tmp_path):
    (tmp_path / "load_gassco.py").write_text(
        '''
from airflow import DAG

dag = DAG(dag_id="load_gassco", description="Gassco")

def load_data():
    sql = "INSERT INTO src_gassco.gassco_flows VALUES (1)"

if __name__ == "__main__":
    LANDING = "/data/landing/should_ignore"
    sql = "INSERT INTO src_ignore.ignored VALUES (1)"
''',
        encoding="utf-8",
    )
    run = AirflowDagsLineageAdapter(
        store,
        DwhCollectorSettings(airflow_dags_root=str(tmp_path), airflow_lineage_mode="code"),
    ).collect(now)
    assert run.status == CollectorStatus.SUCCESS
    assert run.details.get("writes", 0) == 1
    assert run.details.get("storages", 0) == 0
    process = store.find_by_identity("airflow_dags", airflow_process_identity("load_gassco")[1])
    assert process is not None
    writes = store.list_relationships(asset_id=process.id, types={RelationshipType.WRITES_TO})
    table = store.get_asset(writes[0].to_asset_id)
    assert table is not None
    assert table.name == "gassco_flows"
    assert store.find_by_qualified_name("storage:/data/landing/should_ignore") is None
    assert store.find_by_qualified_name("unresolved:dwh.src_ignore.ignored") is None


def test_airflow_code_mode_ignores_web_asset_paths(store, now, tmp_path):
    (tmp_path / "load_epdk.py").write_text(
        '''
from airflow import DAG

dag = DAG(dag_id="load_epdk", description="EPDK")
WORD_ICON = "/Content/img/word.png"
ROUTE = "/Detay/DownloadDocument?id=1"

def filter_uloaded_files(html_filename):
    images = soup.find_all("img")
    word_imgs = [img for img in images if img.attrs["src"] == "/Content/img/word.png"]
    sql = "INSERT INTO src_epdk.docs VALUES (1)"
''',
        encoding="utf-8",
    )
    run = AirflowDagsLineageAdapter(
        store,
        DwhCollectorSettings(airflow_dags_root=str(tmp_path), airflow_lineage_mode="code"),
    ).collect(now)
    assert run.status == CollectorStatus.SUCCESS
    assert run.details.get("storages", 0) == 0
    assert store.find_by_qualified_name("storage:/Content/img/word.png") is None
    process = store.find_by_identity("airflow_dags", airflow_process_identity("load_epdk")[1])
    assert process is not None


def test_airflow_adapter_ignores_pandas_merge(store, now, tmp_path):
    CatalogCollector(store, FakeMetadataProvider(_catalog_objects())).run(now)
    (tmp_path / "load_gnph.py").write_text(
        '''
from airflow import DAG
import pandas as pd

dag = DAG(dag_id="load_gnph", description="GNPH")

def load_data():
    df = pd.DataFrame()
    other = pd.DataFrame()
    df.merge(other, on="date")
''',
        encoding="utf-8",
    )
    run = AirflowDagsLineageAdapter(
        store,
        DwhCollectorSettings(airflow_dags_root=str(tmp_path), airflow_lineage_mode="code"),
    ).collect(now)
    assert run.status == CollectorStatus.SUCCESS
    assert run.details.get("writes", 0) == 0
    assert store.find_by_identity("airflow_dags", airflow_process_identity("load_gnph")[1]) is None


def test_parse_module_ignores_invalid_string_escapes(tmp_path):
    path = tmp_path / "platts.py"
    path.write_text(
        'PATTERN = "^x_(?P<year>\\d{4}).csv$"\n'
        'PATH = "D:\\\\temp\\\\airflow_files\\epdk\\plot.png"\n',
        encoding="utf-8",
    )
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        facts = parse_module(path, path.read_text(encoding="utf-8"))
    assert facts is not None
    assert not any(issubclass(item.category, SyntaxWarning) for item in caught)


def test_parse_dag_meta():
    meta = parse_dag_meta(
        '''
dag = DAG(
    dag_id='load_platts_egd',
    tags=["platts_egd", "egd"],
    description="Загрузка данных  Platts European Gas Daily",
)
'''
    )
    assert meta.dag_id == "load_platts_egd"
    assert meta.description == "Загрузка данных Platts European Gas Daily"


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
