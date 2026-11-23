"""Independent loader fixtures: no dependency on any checked-out source sample."""

import textwrap

import pytest

from domains.catalog.lineage_adapters import python_loader_analysis as analysis_module
from domains.catalog.lineage_adapters.python_loader_analysis import (
    AmbiguousModule,
    PythonLoaderAnalyzer,
    PythonModuleRoots,
)
from domains.catalog.lineage_adapters.python_modules import PythonModulesLineageAdapter
from domains.catalog.models import Asset, AssetType, RelationshipType
from settings.portal import DwhCollectorSettings


def _sources(root, sources):
    for name, source in sources.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(textwrap.dedent(source), encoding="utf-8")


def _analyze(root, sources, entry="Loader", filename="loader.py"):
    _sources(root, sources)
    return PythonLoaderAnalyzer(root).analyze(root / filename, entry)


def _targets(result):
    return {(ref.schema, ref.name) for ref in result.refs}


def _excel_loader_sources(writer):
    return {
        "lib/DB/base.py": """
            from sqlalchemy.dialects.postgresql import insert
            class InboxBase:
                __table_args__ = {'schema': 'inbox'}
                @classmethod
                def upsert_data(cls, df, session):
                    table = cls.__table__
                    session.execute(insert(table).values(df).on_conflict_do_update(set_={}))
        """,
        "lib/DB/inbox/inbox_argus_data.py": """
            from lib.DB.base import InboxBase
            class InboxArgusData(InboxBase):
                __tablename__ = 'argus_data'
        """,
        "lib/files/base_excel_template_model.py": f"""
            class BaseExcelTemplateFileModel:
                @classmethod
                def load_file(cls, df, session):
                    {writer}
        """,
        "loader.py": """
            from lib.DB.inbox.inbox_argus_data import InboxArgusData
            from lib.files.base_excel_template_model import BaseExcelTemplateFileModel
            class ArgusDataFileModel(BaseExcelTemplateFileModel):
                _TABLE_NAME = InboxArgusData.__tablename__
                _INBOX_CLASS = InboxArgusData
                _SAVE_METHOD = InboxArgusData.upsert_data
                _COL_NAME_ACTION_DATE = InboxArgusData.action_date.name
            class Loader(ArgusDataFileModel):
                pass
            class Sibling(BaseExcelTemplateFileModel):
                _TABLE_NAME = 'not_written'
        """,
    }


@pytest.mark.parametrize("renamed", [False, True])
@pytest.mark.parametrize(
    "writer,pattern",
    [
        ("cls._SAVE_METHOD(df, session)", "orm"),
        ("cls._INBOX_CLASS.upsert_data(df, session)", "orm"),
        ("df.to_sql(cls._TABLE_NAME, schema=cls._INBOX_CLASS.__table__.schema)", "to_sql"),
        ("df.to_sql(cls._INBOX_CLASS.__table__.name, schema='inbox')", "to_sql"),
    ],
)
def test_excel_loader_orm_attributes_reach_inherited_writer(tmp_path, writer, pattern, renamed):
    sources = _excel_loader_sources(writer)
    if renamed:
        for old, new in (
            ("_TABLE_NAME", "destination_name"),
            ("_INBOX_CLASS", "destination_model"),
            ("_SAVE_METHOD", "persist_rows"),
        ):
            sources = {name: source.replace(old, new) for name, source in sources.items()}
    result = _analyze(tmp_path, sources)
    assert _targets(result) == {("inbox", "argus_data")}
    assert not result.diagnostics
    assert {item["pattern"] for item in result.evidence} == {pattern}


def test_excel_loader_attributes_without_reachable_write_are_not_targets(tmp_path):
    result = _analyze(tmp_path, _excel_loader_sources("logger.info(cls._TABLE_NAME)"))
    assert not result.refs
    assert not result.evidence


@pytest.mark.parametrize(
    "declaration",
    ["__table_args__ = RUNTIME_OPTIONS", "__table__ = RUNTIME_TABLE"],
)
def test_orm_table_metadata_does_not_replace_explicit_unknowns(tmp_path, declaration):
    result = _analyze(
        tmp_path,
        {"loader.py": f"""
            from sqlalchemy import insert
            class Model:
                __tablename__ = 'not_proven'
                {declaration}
            def load_file(session):
                session.execute(insert(Model.__table__))
        """},
        entry="load_file",
    )
    assert not result.refs
    assert "WRITE_TARGET_UNKNOWN" in {item["code"] for item in result.diagnostics}


@pytest.mark.parametrize("mode", ["catalog", "code"])
def test_excel_loader_adapter_persists_write_on_same_process(store, now, tmp_path, mode):
    _sources(tmp_path, _excel_loader_sources("cls._SAVE_METHOD(df, session)"))
    process = _registry_process(store, now)
    process.attributes["entry_point"] = "Loader"
    store.upsert_asset(process)
    table = store.upsert_asset(
        Asset(
            asset_type=AssetType.TABLE,
            name="argus_data",
            qualified_name="dwh.inbox.argus_data",
            source_provider="postgres",
            identity_key="inbox.argus_data",
            first_seen_at=now,
            last_seen_at=now,
            attributes={"schema": "inbox"},
        )
    )
    adapter = PythonModulesLineageAdapter(
        store,
        DwhCollectorSettings(python_modules_root=str(tmp_path), python_modules_lineage_mode=mode),
    )
    for _ in range(2):
        run = adapter.collect(now)
        assert run.status == "SUCCESS"
        edges = store.list_relationships(asset_id=process.id, types={RelationshipType.WRITES_TO})
        assert len(edges) == 1
        assert edges[0].to_asset_id == table.id
        stored = store.get_asset(process.id)
        assert stored.identity_key == process.identity_key
        assert stored.attributes["write_evidence"] == [
            {
                "schema": "inbox",
                "table": "argus_data",
                "file": "lib/DB/base.py",
                "line": 8,
                "pattern": "orm",
            }
        ]
        assert str(tmp_path) not in str(stored.attributes)
    assert (
        len([asset for asset in store.assets.values() if asset.asset_type == AssetType.PROCESS])
        == 1
    )


def test_selected_subclass_imported_orm_inherited_writer_and_secondary(tmp_path):
    result = _analyze(
        tmp_path,
        {
            "pkg/__init__.py": "",
            "pkg/constants.py": "SCHEMA = 'facts'\nOPTIONS = {'schema': SCHEMA}\nTABLE = 'flows'",
            "pkg/aliases.py": "from .constants import OPTIONS as SETTINGS, TABLE as NAME",
            "pkg/models.py": """
            from .aliases import SETTINGS, NAME
            class Base:
                __table_args__ = SETTINGS
            class Model(Base):
                __tablename__ = NAME
            class ReadOnly(Base):
                __tablename__ = 'read_only'
        """,
            "pkg/base.py": """
            class Base:
                @classmethod
                def load_file(cls, df):
                    cls.save(df, cls._TABLE_NAME, cls._DB_SCHEMA)
                    cls.extra(df)
                @classmethod
                def save(cls, df, table, schema):
                    df.to_sql(table, schema=schema)
        """,
            "loader.py": """
            from pkg.base import Base
            from pkg.models import Model as Target, ReadOnly
            class Loader(Base):
                _TABLE_NAME: str = Target.__tablename__
                _DB_SCHEMA = Target.__table_args__['schema']
                @classmethod
                def extra(cls, df):
                    unused = ReadOnly()
                    df.to_sql('secondary', schema=Target.__table_args__.get('schema'))
            class Sibling(Base):
                _TABLE_NAME = 'unrelated'
                _DB_SCHEMA = 'other'
        """,
        },
    )
    assert _targets(result) == {("facts", "flows"), ("facts", "secondary")}
    assert not result.diagnostics
    assert {e["pattern"] for e in result.evidence} == {"to_sql"}
    assert all(e["line"] > 0 and not e["file"].startswith("/") for e in result.evidence)


def test_helper_parameters_configuration_loops_and_tuple_unpacking(tmp_path):
    result = _analyze(
        tmp_path,
        {"loader.py": """
        def save(schema, table, df):
            df.to_sql(name=table, schema=schema)
        class Loader:
            SHEETS = {'one': ('sol', 'edges'), 'two': ('sol', 'nodes')}
            @classmethod
            def load_file(cls, df):
                df_tables = {}
                for sheet, schema_table in cls.SHEETS.items():
                    df_tables[sheet] = (df, *schema_table)
                for sheet, data in df_tables.items():
                    frame, schema, table = data
                    save(schema, table, frame)
                cls.secondary(df)
            @classmethod
            def secondary(cls, df):
                schema, table = 'inbox', 'history'
                save(table=table, df=df, schema=schema)
    """},
    )
    assert _targets(result) == {("sol", "edges"), ("sol", "nodes"), ("inbox", "history")}
    assert not result.diagnostics


def test_super_dispatch_local_helpers_and_all_sql_and_dataframe_writes(tmp_path):
    result = _analyze(
        tmp_path,
        {"loader.py": """
        from sqlalchemy import text
        class Base:
            @classmethod
            def load_file(cls, df, conn):
                df.to_sql(cls.TABLE, schema=cls.SCHEMA)
        class Loader(Base):
            SCHEMA, TABLE = 'inbox', 'first'
            @classmethod
            def load_file(cls, df, conn):
                super().load_file(df, conn)
                cls.save(conn, 'inbox', 'second')
            @staticmethod
            def save(conn, schema, table):
                conn.execute(text(f'INSERT INTO "{schema}"."{table}" VALUES (1)'))
    """},
    )
    assert _targets(result) == {("inbox", "first"), ("inbox", "second")}


def test_namespaced_models_orm_writes_not_read_only_references(tmp_path):
    result = _analyze(
        tmp_path,
        {
            "a.py": "class Model:\n    __tablename__='written'\n    __table_args__={'schema':'raw'}",
            "b.py": "class Model:\n    __tablename__='read_only'\n    __table_args__={'schema':'raw'}",
            "loader.py": """
            from sqlalchemy.dialects.postgresql import insert as pg_insert
            import a as first
            from b import Model
            def load_file(session):
                model = Model()
                session.query(Model)
                session.execute(pg_insert(first.Model))
        """,
        },
        entry="load_file",
    )
    assert _targets(result) == {("raw", "written")}


@pytest.mark.parametrize(
    "entry,code", [(None, "ENTRY_POINT_AMBIGUOUS"), ("Missing", "ENTRY_POINT_MISSING")]
)
def test_missing_and_ambiguous_entry_never_scans_siblings(tmp_path, entry, code):
    result = _analyze(
        tmp_path,
        {"loader.py": """
        class One:
            def load_file(self):
                df.to_sql('one', schema='raw')
        class Two:
            def load_file(self):
                df.to_sql('two', schema='raw')
    """},
        entry,
    )
    assert not result.refs
    assert code in {d["code"] for d in result.diagnostics}


def test_unambiguous_legacy_function_and_class_are_inferred(tmp_path):
    for source in (
        "def load_data():\n    df.to_sql('legacy', schema='raw')",
        "class Legacy:\n    def load_file(self):\n        df.to_sql('legacy', schema='raw')",
    ):
        result = _analyze(tmp_path, {"loader.py": source}, entry=None)
        assert _targets(result) == {("raw", "legacy")}
        assert not result.diagnostics


def test_unknown_values_unused_sql_docstrings_and_main_do_not_become_targets(tmp_path):
    result = _analyze(
        tmp_path,
        {"loader.py": """
        raise RuntimeError('must never execute source')
        class Loader:
            def load_file(self, runtime_table, runtime_schema):
                '''INSERT INTO fake.docstring VALUES (1)'''
                unused_sql = 'INSERT INTO fake.unused VALUES (1)'
                df.to_sql(runtime_table, schema='raw')
                df.to_sql('known_name', schema=runtime_schema)
        if __name__ == '__main__':
            df.to_sql('main_only', schema='fake')
    """},
    )
    assert not result.refs
    assert {d["code"] for d in result.diagnostics} == {"WRITE_TARGET_UNKNOWN"}


def test_calls_and_import_cycles_terminate_with_diagnostics(tmp_path):
    result = _analyze(
        tmp_path,
        {
            "a.py": "from b import SCHEMA",
            "b.py": "from a import SCHEMA",
            "loader.py": """
            from a import SCHEMA
            def recursive():
                recursive()
            def load_file():
                recursive()
                df.to_sql('known', schema=SCHEMA)
        """,
        },
        "load_file",
    )
    assert not result.refs
    assert {"CALL_CYCLE", "RESOLUTION_CYCLE", "WRITE_TARGET_UNKNOWN"} <= {
        d["code"] for d in result.diagnostics
    }


@pytest.mark.parametrize(
    "limit",
    ["MAX_STEPS", "MAX_CALLS", "MAX_MODULES", "MAX_NODES", "MAX_FILE_BYTES", "MAX_ITERATIONS"],
)
def test_analysis_budgets_are_explicit_diagnostics(tmp_path, monkeypatch, limit):
    monkeypatch.setattr(analysis_module, limit, 0)
    result = _analyze(
        tmp_path,
        {"loader.py": """
        class Loader:
            def load_file(self):
                for table in ('one', 'two'):
                    df.to_sql(table, schema='raw')
    """},
    )
    assert not result.refs
    assert {d["code"] for d in result.diagnostics} & {"ANALYSIS_LIMIT", "SOURCE_LIMIT"}


def test_malformed_and_missing_modules_are_diagnostic(tmp_path):
    result = _analyze(tmp_path, {"loader.py": "def not_valid("})
    assert not result.refs
    assert result.diagnostics[0]["code"] == "MODULE_UNAVAILABLE"
    result = PythonLoaderAnalyzer(tmp_path).analyze(tmp_path / "missing.py", "Loader")
    assert result.diagnostics[0]["code"] == "MODULE_UNAVAILABLE"


def test_symlink_cannot_import_outside_root(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    _sources(tmp_path, {"outside.py": "TABLE = 'secret'"})
    (root / "outside.py").symlink_to(tmp_path / "outside.py")
    result = _analyze(
        root,
        {"loader.py": """
        from outside import TABLE
        def load_file():
            df.to_sql(TABLE, schema='raw')
    """},
        "load_file",
    )
    assert not result.refs
    assert "outside.py" not in result.source_files


def test_unknown_sql_payload_preserves_only_known_target(tmp_path):
    result = _analyze(
        tmp_path,
        {"loader.py": """
        from sqlalchemy import text
        def load_file(conn, columns, values, runtime_table):
            conn.execute(text(f"INSERT INTO raw.known ({columns}) VALUES ({values})"))
            conn.execute(text(f"INSERT INTO raw.{runtime_table} VALUES (1)"))
    """},
        "load_file",
    )
    assert _targets(result) == {("raw", "known")}
    assert "WRITE_TARGET_UNKNOWN" in {d["code"] for d in result.diagnostics}


def test_unused_insert_and_declaration_helper_are_not_writes(tmp_path):
    result = _analyze(
        tmp_path,
        {"loader.py": """
        from sqlalchemy import insert
        class Model:
            __tablename__ = 'unused'
            __table_args__ = {'schema': 'raw'}
        def declare():
            df.to_sql('unreachable', schema='raw')
        SETTING = declare()
        class Loader:
            _SETTING = SETTING
            def load_file(self):
                unused = insert(Model)
    """},
    )
    assert not result.refs


def test_local_wrapper_name_does_not_imply_write(tmp_path):
    result = _analyze(
        tmp_path,
        {"loader.py": """
        def save_to_db(schema, table, df):
            logger.info(table)
        def load_file():
            save_to_db('raw', 'not_written', df)
    """},
        "load_file",
    )
    assert not result.refs


def test_runtime_branch_assignments_do_not_create_guessed_identity(tmp_path):
    result = _analyze(
        tmp_path,
        {"loader.py": """
        def load_file(runtime):
            if runtime:
                table = 'one'
            else:
                table = 'two'
            df.to_sql(table, schema='raw')
    """},
        "load_file",
    )
    assert not result.refs
    assert "WRITE_TARGET_UNKNOWN" in {d["code"] for d in result.diagnostics}


def test_finite_starred_and_keyword_helper_arguments(tmp_path):
    result = _analyze(
        tmp_path,
        {"loader.py": """
        def save(schema, table, df=None):
            df.to_sql(table, schema=schema)
        def load_file():
            target = ('raw', 'one')
            save(*target)
            save(**{'schema': 'raw', 'table': 'two'})
    """},
        "load_file",
    )
    assert _targets(result) == {("raw", "one"), ("raw", "two")}


def test_unknown_orm_schema_cannot_fall_back_to_unqualified_name(tmp_path):
    result = _analyze(
        tmp_path,
        {"loader.py": """
        from sqlalchemy import insert
        class Base:
            __table_args__ = RUNTIME_OPTIONS
        class Model(Base):
            __tablename__ = 'not_proven'
        def load_file(session):
            session.execute(insert(Model))
    """},
        "load_file",
    )
    assert not result.refs
    assert "WRITE_TARGET_UNKNOWN" in {d["code"] for d in result.diagnostics}


@pytest.mark.parametrize("mode", ["catalog", "code"])
def test_adapter_qualified_miss_never_falls_back_to_another_schema(store, now, tmp_path, mode):
    _sources(
        tmp_path,
        {"loader.py": """
        def load_file():
            df.to_sql('measurements', schema='inbox')
    """},
    )
    process = store.upsert_asset(
        Asset(
            asset_type=AssetType.PROCESS,
            name="loader",
            qualified_name="process:one",
            source_provider="extraction_registry",
            identity_key="process:one",
            first_seen_at=now,
            last_seen_at=now,
            attributes={"handler_type": "Python", "module": "loader", "entry_point": "load_file"},
        )
    )
    other = store.upsert_asset(
        Asset(
            asset_type=AssetType.TABLE,
            name="measurements",
            qualified_name="dwh.other.measurements",
            source_provider="postgres",
            identity_key="other.measurements",
            first_seen_at=now,
            last_seen_at=now,
            attributes={"schema": "other"},
        )
    )
    run = PythonModulesLineageAdapter(
        store,
        DwhCollectorSettings(
            python_modules_root=str(tmp_path),
            python_modules_lineage_mode=mode,
        ),
    ).collect(now)
    assert run.status != "FAILED"
    edges = store.list_relationships(asset_id=process.id, types={RelationshipType.WRITES_TO})
    assert all(edge.to_asset_id != other.id for edge in edges)
    assert len(edges) == (1 if mode == "code" else 0)
    if edges:
        target = store.get_asset(edges[0].to_asset_id)
        assert target.attributes["unresolved"] is True
        assert target.attributes["schema"] == "inbox"
    assert store.get_asset(process.id).attributes["write_evidence"][0]["file"] == "loader.py"


def _registry_process(store, now, module="loader"):
    return store.upsert_asset(
        Asset(
            asset_type=AssetType.PROCESS,
            name=module,
            qualified_name=f"process:{module}",
            source_provider="extraction_registry",
            identity_key=f"process:{module}",
            first_seen_at=now,
            last_seen_at=now,
            attributes={"handler_type": "Python", "module": module, "entry_point": "load_file"},
        )
    )


def test_roots_trim_empty_normalized_and_symlink_duplicates(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    (root / "child").mkdir()
    alias = tmp_path / "alias"
    alias.symlink_to(root, target_is_directory=True)
    _sources(root, {"loader.py": "def load_file():\n    df.to_sql('one', schema='raw')"})
    sources = PythonModuleRoots.from_setting(f" ; {root} ; ; {root}/child/.. ; {alias}; {root} ; ")
    assert sources.roots == [root.resolve()]
    assert not sources.invalid
    assert sources.resolve("loader") == root / "loader.py"
    result = PythonLoaderAnalyzer(sources).analyze(root / "loader.py", "load_file")
    assert _targets(result) == {("raw", "one")}
    assert result.source_files == ["loader.py"]


@pytest.mark.parametrize("position", [2, 5])
def test_adapter_finds_entry_in_any_configured_root(store, now, tmp_path, position):
    roots = [tmp_path / str(index) for index in range(5)]
    for root in roots:
        root.mkdir()
    _sources(
        roots[position - 1], {"loader.py": "def load_file():\n    df.to_sql('one', schema='raw')"}
    )
    process = _registry_process(store, now)
    run = PythonModulesLineageAdapter(
        store,
        DwhCollectorSettings(
            python_modules_root=" ; ".join(map(str, roots)), python_modules_lineage_mode="code"
        ),
    ).collect(now)
    assert run.status == "SUCCESS"
    assert run.details["writes"] == 1
    stored = store.get_asset(process.id)
    assert stored.identity_key == process.identity_key
    assert stored.attributes["source_files"] == [f"root_{position}/loader.py"]
    assert stored.attributes["write_evidence"][0]["file"] == f"root_{position}/loader.py"
    assert str(tmp_path) not in str(stored.attributes)


def test_adapter_entry_collision_is_diagnostic_not_first_match(store, now, tmp_path):
    roots = [tmp_path / "one", tmp_path / "two"]
    for root in roots:
        _sources(root, {"loader.py": "def load_file():\n    df.to_sql('wrong', schema='raw')"})
    process = _registry_process(store, now)
    run = PythonModulesLineageAdapter(
        store,
        DwhCollectorSettings(
            python_modules_root=";".join(map(str, roots)), python_modules_lineage_mode="code"
        ),
    ).collect(now)
    assert run.status != "FAILED"
    assert not store.list_relationships(asset_id=process.id, types={RelationshipType.WRITES_TO})
    assert "MODULE_AMBIGUOUS" in {d.code for d in store.list_diagnostics(process.id)}
    assert store.get_asset(process.id).attributes["source_files"] == []


@pytest.mark.parametrize(
    "statement,call",
    [
        ("from writer import save", "save()"),
        ("import writer as helper", "helper.save()"),
        ("import helpers.writer", "helpers.writer.save()"),
        ("import helpers", "helpers.writer.save()"),
    ],
)
def test_unique_absolute_dependency_across_roots(tmp_path, statement, call):
    first, second = tmp_path / "first", tmp_path / "second"
    _sources(first, {"loader.py": f"{statement}\ndef load_file():\n    {call}"})
    _sources(
        second,
        {
            "writer.py": "def save():\n    df.to_sql('cross_root', schema='raw')",
            "helpers/writer.py": "def save():\n    df.to_sql('cross_root', schema='raw')",
        },
    )
    result = PythonLoaderAnalyzer([first, second]).analyze(first / "loader.py", "load_file")
    assert _targets(result) == {("raw", "cross_root")}
    assert not result.diagnostics
    assert result.evidence[0]["file"].startswith("root_2/")
    assert str(tmp_path) not in str(result.evidence)


@pytest.mark.parametrize(
    "statement,call",
    [
        ("from writer import save", "save()"),
        ("import writer as helper", "helper.save()"),
        ("from writer import to_sql", "to_sql('wrong', schema='raw')"),
        ("import writer\nto_sql = writer.save", "to_sql('wrong', schema='raw')"),
        ("import writer", "writer.save().to_sql('wrong', schema='raw')"),
    ],
)
def test_ambiguous_absolute_dependency_never_selects_a_writer(tmp_path, statement, call):
    first, second = tmp_path / "first", tmp_path / "second"
    for root in (first, second):
        _sources(root, {"writer.py": "def save():\n    df.to_sql('wrong', schema='raw')"})
    _sources(first, {"loader.py": f"{statement}\ndef load_file():\n    {call}"})
    result = PythonLoaderAnalyzer([first, second]).analyze(first / "loader.py", "load_file")
    assert not result.refs
    assert "MODULE_AMBIGUOUS" in {d["code"] for d in result.diagnostics}
    assert all(not name.endswith("writer.py") for name in result.source_files)


def test_relative_dependencies_stay_in_declaring_package_and_root(tmp_path):
    first, second = tmp_path / "first", tmp_path / "second"
    for root, table in ((first, "owned"), (second, "wrong")):
        _sources(
            root,
            {
                "pkg/__init__.py": "",
                "pkg/helper.py": f"TABLE = '{table}'",
            },
        )
    _sources(
        first,
        {"pkg/loader.py": """
        from .helper import TABLE
        def load_file():
            df.to_sql(TABLE, schema='raw')
    """},
    )
    result = PythonLoaderAnalyzer([first, second]).analyze(first / "pkg/loader.py", "load_file")
    assert _targets(result) == {("raw", "owned")}
    assert not result.diagnostics
    assert "root_2/pkg/helper.py" not in result.source_files
    (first / "pkg/helper.py").unlink()
    result = PythonLoaderAnalyzer([first, second]).analyze(first / "pkg/loader.py", "load_file")
    assert not result.refs


def test_duplicate_package_cannot_supply_unique_children_from_different_roots(tmp_path):
    first, second = tmp_path / "first", tmp_path / "second"
    _sources(first, {"pkg/__init__.py": "", "pkg/one.py": "VALUE = 1"})
    _sources(second, {"pkg/__init__.py": "", "pkg/two.py": "VALUE = 2"})
    sources = PythonModuleRoots([first, second])
    with pytest.raises(AmbiguousModule):
        sources.resolve("pkg.two")


@pytest.mark.parametrize("value", ["", " ; ; ", "missing"])
def test_no_usable_roots_skip_successfully(store, now, tmp_path, value):
    setting = str(tmp_path / value) if value == "missing" else value
    run = PythonModulesLineageAdapter(
        store, DwhCollectorSettings(python_modules_root=setting)
    ).collect(now)
    assert run.status == "SUCCESS"
    assert run.details["skipped"] is True
    if value == "missing":
        assert "MODULES_ROOT_UNAVAILABLE" in {d.code for d in store.list_diagnostics()}


def test_missing_root_does_not_block_valid_root(store, now, tmp_path):
    root = tmp_path / "valid"
    _sources(root, {"loader.py": "def load_file():\n    df.to_sql('one', schema='raw')"})
    _registry_process(store, now)
    run = PythonModulesLineageAdapter(
        store,
        DwhCollectorSettings(
            python_modules_root=f"{tmp_path / 'absent'};{root}", python_modules_lineage_mode="code"
        ),
    ).collect(now)
    assert run.status == "PARTIAL"
    assert run.details["writes"] == 1
    diagnostics = store.list_diagnostics()
    assert "MODULES_ROOT_UNAVAILABLE" in {d.code for d in diagnostics}
    assert str(tmp_path) not in str([d.details for d in diagnostics])


def test_code_storage_closure_does_not_pick_ambiguous_dependency(store, now, tmp_path):
    first, second = tmp_path / "first", tmp_path / "second"
    for root in (first, second):
        _sources(root, {"paths.py": "PATH = '/data/landing/ambiguous'"})
    _sources(
        first,
        {"loader.py": """
        import paths
        def load_file():
            df.to_sql('known', schema='raw')
    """},
    )
    _registry_process(store, now)
    run = PythonModulesLineageAdapter(
        store,
        DwhCollectorSettings(
            python_modules_root=f"{first};{second}", python_modules_lineage_mode="code"
        ),
    ).collect(now)
    assert run.status == "PARTIAL"
    assert run.details["writes"] == 1
    assert run.details["storages"] == 0
    assert "MODULE_AMBIGUOUS" in {d.code for d in store.list_diagnostics()}


def test_overlapping_roots_deduplicate_physical_module_and_confine_relative_import(tmp_path):
    root = tmp_path / "root"
    nested = root / "nested"
    _sources(root, {"outside.py": "TABLE = 'wrong'"})
    _sources(
        nested,
        {"loader.py": """
        from ..outside import TABLE
        def load_file():
            df.to_sql(TABLE, schema='raw')
    """},
    )
    sources = PythonModuleRoots([root, nested])
    assert sources.owner(nested / "loader.py") == nested
    result = PythonLoaderAnalyzer(sources).analyze(nested / "loader.py", "load_file")
    assert not result.refs
    assert result.source_files == ["root_2/loader.py"]


def test_same_relative_filenames_keep_separate_values_and_provenance(tmp_path):
    first, second = tmp_path / "first", tmp_path / "second"
    _sources(
        first,
        {
            "common.py": "def save():\n    df.to_sql('one', schema='raw')",
            "loader.py": """
            from .common import save
            from writer import write
            def load_file():
                save()
                write()
        """,
        },
    )
    _sources(
        second,
        {
            "common.py": "def save():\n    df.to_sql('two', schema='raw')",
            "writer.py": "from .common import save\ndef write():\n    save()",
        },
    )
    result = PythonLoaderAnalyzer([first, second]).analyze(first / "loader.py", "load_file")
    assert _targets(result) == {("raw", "one"), ("raw", "two")}
    assert not result.diagnostics
    assert {item["file"] for item in result.evidence} == {"root_1/common.py", "root_2/common.py"}


def test_lazy_absolute_package_child_cannot_hide_duplicate_module(tmp_path):
    first, second = tmp_path / "first", tmp_path / "second"
    _sources(
        first,
        {
            "pkg/__init__.py": "",
            "pkg/writer.py": "def to_sql(*args, **kwargs):\n    pass",
            "loader.py": "import pkg\ndef load_file():\n    pkg.writer.to_sql('wrong', schema='raw')",
        },
    )
    _sources(second, {"pkg/writer.py": "def to_sql(*args, **kwargs):\n    pass"})
    result = PythonLoaderAnalyzer([first, second]).analyze(first / "loader.py", "load_file")
    assert not result.refs
    assert "MODULE_AMBIGUOUS" in {d["code"] for d in result.diagnostics}


def test_code_storage_unique_cross_root_and_process_caches_are_isolated(store, now, tmp_path):
    first, second = tmp_path / "first", tmp_path / "second"
    _sources(
        first,
        {
            "one.py": "import paths\ndef load_file():\n    pass",
            "two.py": "def load_file():\n    pass",
        },
    )
    _sources(second, {"paths.py": "PATH = '/data/landing/unique'"})
    one = _registry_process(store, now, "one")
    two = _registry_process(store, now, "two")
    run = PythonModulesLineageAdapter(
        store,
        DwhCollectorSettings(
            python_modules_root=f"{first};{second}", python_modules_lineage_mode="code"
        ),
    ).collect(now)
    assert run.status != "FAILED"
    assert run.details["storages"] == 1
    assert len(store.list_relationships(asset_id=one.id, types={RelationshipType.READS_FROM})) == 1
    assert not store.list_relationships(asset_id=two.id, types={RelationshipType.READS_FROM})
    assert "root_2/paths.py" in store.get_asset(one.id).attributes["source_files"]
    assert store.get_asset(two.id).attributes["source_files"] == ["root_1/two.py"]
