"""Independent loader fixtures: no dependency on any checked-out source sample."""

import textwrap

import pytest

from domains.catalog.lineage_adapters import python_loader_analysis as analysis_module
from domains.catalog.lineage_adapters.python_loader_analysis import PythonLoaderAnalyzer
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
