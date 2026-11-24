"""Source-only regression coverage for Python loader target resolution."""

import textwrap

import pytest

from domains.catalog.lineage_adapters.python_loader_analysis import PythonLoaderAnalyzer
from domains.catalog.lineage_adapters.python_sql_writes import sql_write_targets


def analyze(tmp_path, sources, entry="load", filename="loader.py"):
    if isinstance(sources, str):
        sources = {filename: sources}
    for name, source in sources.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(textwrap.dedent(source), encoding="utf-8")
    return PythonLoaderAnalyzer(tmp_path).analyze(tmp_path / filename, entry)


def targets(result):
    return {(ref.schema, ref.name) for ref in result.refs}


@pytest.mark.parametrize(
    "body, expected",
    [
        ("for x in (1,):\n    return\ndf.to_sql('wrong')", set()),
        ("for x in (1,):\n    break\nelse:\n    df.to_sql('wrong')", set()),
        ("for x in (1,):\n    continue\n    df.to_sql('wrong')", set()),
        ("if flag:\n    return\nelse:\n    return\ndf.to_sql('wrong')", set()),
        ("if False:\n    df.to_sql('wrong')\nelse:\n    df.to_sql('ok')", {(None, "ok")}),
        ("False and df.to_sql('wrong')", set()),
        ("True or df.to_sql('wrong')", set()),
        ("df.to_sql('wrong') if False else None", set()),
        ("while False:\n    df.to_sql('wrong')\nelse:\n    df.to_sql('ok')", {(None, "ok")}),
        ("try:\n    return\nfinally:\n    df.to_sql('ok')\ndf.to_sql('wrong')", {(None, "ok")}),
        ("raise RuntimeError()\ndf.to_sql('wrong')", set()),
        ("if flag:\n    return\nelse:\n    table = 'ok'\ndf.to_sql(table)", {(None, "ok")}),
        ("while True:\n    return\ndf.to_sql('wrong')", set()),
        ("while True:\n    break\nelse:\n    df.to_sql('wrong')", set()),
        ("assert False\ndf.to_sql('wrong')", set()),
        ("table = 'old'\nmatch flag:\n    case 1:\n        table = 'new'\ndf.to_sql(table)", set()),
    ],
)
def test_control_flow_reachability(tmp_path, body, expected):
    result = analyze(tmp_path, "def load():\n" + textwrap.indent(body, "    "))
    assert targets(result) == expected


def test_inherited_constructor_and_adjacent_config(tmp_path):
    result = analyze(
        tmp_path,
        {
            "pkg/__init__.py": "",
            "pkg/config.py": """
                class ParentSettings:
                    schema = 'inbox'
                class Settings(ParentSettings):
                    table = 'market_prices'
                CONFIG = Settings()
            """,
            "pkg/base.py": """
                from .config import CONFIG
                class Writer:
                    def __init__(self, settings=CONFIG):
                        self.settings = settings
                    @property
                    def target(self):
                        return self.settings.table
                    def load_file(self, frame):
                        frame.to_sql(self.target, schema=self.settings.schema)
            """,
            "loader.py": """
                from pkg.base import Writer
                class Loader(Writer): pass
                class Sibling(Writer):
                    def load_file(self, frame):
                        frame.to_sql('not_selected')
            """,
        },
        entry="Loader",
    )
    assert targets(result) == {("inbox", "market_prices")}
    assert result.evidence == [{"schema": "inbox", "table": "market_prices", "file": "pkg/base.py", "line": 10, "pattern": "to_sql"}]
    assert set(result.source_files) >= {"loader.py", "pkg/base.py", "pkg/config.py"}


def test_base_constructor_super_uses_actual_receiver(tmp_path):
    result = analyze(tmp_path, """
        class Base:
            def __init__(obj, namespace):
                obj.schema = namespace
            def load_file(obj, df):
                df.to_sql(obj.table, schema=obj.schema)
        class Loader(Base):
            def __init__(this):
                super().__init__('raw')
                this.table = 'measurements'
    """, entry="Loader")
    assert targets(result) == {("raw", "measurements")}


def test_c3_prefers_nearest_member_in_diamond(tmp_path):
    result = analyze(tmp_path, """
        class Root:
            target = 'root'
        class Left(Root):
            pass
        class Right(Root):
            target = 'right'
        class Loader(Left, Right):
            def load_file(self, df):
                df.to_sql(self.target, schema='raw')
    """, entry="Loader")
    assert targets(result) == {("raw", "right")}


def test_super_uses_next_class_in_actual_mro(tmp_path):
    result = analyze(tmp_path, """
        class Root:
            @classmethod
            def get_name(cls): return 'root'
        class Left(Root):
            @classmethod
            def get_name(cls): return super().get_name()
        class Right(Root):
            @classmethod
            def get_name(cls): return 'right'
        class Loader(Left, Right):
            @classmethod
            def load_file(cls, df): df.to_sql(cls.get_name(), schema='raw')
    """, entry="Loader")
    assert targets(result) == {("raw", "right")}


def test_unknown_base_override_never_uses_lower_priority_parent(tmp_path):
    result = analyze(tmp_path, """
        class First:
            target = runtime()
        class Second:
            target = 'wrong'
        class Loader(First, Second):
            def load_file(self, df):
                df.to_sql(self.target, schema='raw')
    """, entry="Loader")
    assert not result.refs
    assert "WRITE_TARGET_UNKNOWN" in {item["code"] for item in result.diagnostics}


def test_nested_adjacent_class_and_function_local_import(tmp_path):
    result = analyze(tmp_path, {
        "pkg/settings.py": """
            class Names:
                class Price:
                    SCHEMA = 'raw'
                    TABLE = 'prices'
        """,
        "pkg/writer.py": """
            def save(df, config):
                df.to_sql(config.TABLE, schema=config.SCHEMA)
        """,
        "pkg/loader.py": """
            def load(frame):
                from .settings import Names as Config
                from .writer import save as persist
                persist(frame, Config.Price)
        """,
    }, filename="pkg/loader.py")
    assert targets(result) == {("raw", "prices")}
    assert result.evidence[0]["file"] == "pkg/writer.py"


def test_module_constants_resolve_at_definition_time(tmp_path):
    result = analyze(tmp_path, """
        NAME = 'original'
        def get_name(): return NAME
        ALIAS = get_name()
        NAME = 'later'
        def load(df):
            df.to_sql(ALIAS)
    """)
    assert targets(result) == {(None, "original")}


def test_local_name_does_not_fall_back_to_global(tmp_path):
    result = analyze(tmp_path, """
        TABLE = 'wrong'
        def load(df, flag):
            if flag:
                TABLE = 'conditional'
            df.to_sql(TABLE)
    """)
    assert not result.refs


def test_package_export_wins_over_same_named_submodule(tmp_path):
    result = analyze(tmp_path, {
        "pkg/__init__.py": "TABLE = 'exported'",
        "pkg/TABLE.py": "TABLE = 'wrong'",
        "loader.py": "from pkg import TABLE\ndef load(df): df.to_sql(TABLE)",
    })
    assert targets(result) == {(None, "exported")}


def test_inherited_declared_attr_and_metadata(tmp_path):
    result = analyze(tmp_path, {
        "models/base.py": """
            from sqlalchemy import MetaData
            from sqlalchemy.orm import DeclarativeBase, declared_attr as attr
            class Base(DeclarativeBase):
                metadata = MetaData(schema='curated')
                @attr.directive
                def __tablename__(cls):
                    return cls.__name__.lower() + '_history'
        """,
        "models/prices.py": "from .base import Base\nclass Price(Base): pass",
        "loader.py": """
            from models.prices import Price
            from sqlalchemy import insert
            def load(conn):
                conn.execute(insert(Price).values({}))
        """,
    })
    assert targets(result) == {("curated", "price_history")}


@pytest.mark.parametrize("explicit", [False, True])
def test_core_table_from_neighbour_and_explicit_orm_table(tmp_path, explicit):
    result = analyze(tmp_path, {
        "models.py": """
            from sqlalchemy import MetaData, Table
            metadata = MetaData(schema='raw')
            prices = Table('prices', metadata)
            class Model:
                __table__ = prices
                __tablename__ = 'not_used'
        """,
        "loader.py": f"""
            from models import prices, Model
            def load(connection):
                target = {'Model.__table__' if explicit else 'prices'}
                connection.execute(target.insert().values({{}}))
                connection.execute(target.update().where(True).values({{}}))
                connection.execute(target.delete().where(True))
        """,
    })
    assert targets(result) == {("raw", "prices")}
    assert len(result.evidence) == 3


def test_explicit_unknown_orm_table_never_falls_back(tmp_path):
    result = analyze(tmp_path, """
        from sqlalchemy import insert
        class Model:
            __tablename__ = 'wrong'
            __table__ = runtime_table()
        def load():
            session.execute(insert(Model))
    """)
    assert not result.refs
    assert "WRITE_TARGET_UNKNOWN" in {d["code"] for d in result.diagnostics}


def test_orm_sessions_are_resolved_by_origin_not_variable_name(tmp_path):
    result = analyze(tmp_path, """
        from sqlalchemy.orm import Session, sessionmaker
        class Model:
            __tablename__ = 'prices'
            __table_args__ = {'schema': 'raw'}
        def write(s: Session):
            s.bulk_insert_mappings(Model, [])
            s.add(Model())
        def load(engine):
            Factory = sessionmaker(engine)
            with Factory.begin() as strange_name:
                write(strange_name)
                strange_name.add_all([Model(), Model()])
    """)
    assert targets(result) == {("raw", "prices")}
    assert len(result.evidence) == 3


def test_orm_add_on_untyped_collection_is_not_database_write(tmp_path):
    result = analyze(tmp_path, """
        class Model:
            __tablename__ = 'wrong'
        def load(collection):
            collection.add(Model())
    """)
    assert not result.refs
    assert "WRITE_RECEIVER_UNKNOWN" in {item["code"] for item in result.diagnostics}


def test_local_nonwriters_never_promote_method_name(tmp_path):
    result = analyze(tmp_path, """
        class Query:
            def execute(self, statement): return statement
            def to_sql(self, *args): return 'SELECT 1'
        class Other: pass
        def load():
            q = Query()
            q.execute('INSERT INTO wrong.table VALUES (1)')
            q.to_sql('wrong')
            Other().to_sql('wrong')
    """)
    assert not result.refs


@pytest.mark.parametrize("source", [
    "df.to_sql('{prefix}_{suffix}'.format(prefix='market', suffix='prices'), schema='raw')",
    "df.to_sql('%s_%s' % ('market', 'prices'), schema='raw')",
    "df.to_sql('%(prefix)s_%(suffix)s' % {'prefix':'market','suffix':'prices'}, schema='raw')",
    "df.to_sql(f\"{'MARKET'.lower()}_{'prices'}\", schema='raw')",
    "df.to_sql('_'.join(('market','prices')), schema='raw')",
    "df.to_sql(**{**{'name':'market_prices'}, 'schema':'raw'})",
    "df.to_sql(**(dict(name='market_prices') | {'schema':'raw'}))",
])
def test_literal_table_construction(tmp_path, source):
    result = analyze(tmp_path, "def load(df):\n    " + source)
    assert targets(result) == {("raw", "market_prices")}


def test_native_sql_composition_and_bulk_execute(tmp_path):
    result = analyze(tmp_path, """
        from psycopg2 import sql, connect
        from psycopg2.extras import execute_values as batch
        SCHEMA = 'raw'
        TABLE = 'Case Sensitive'
        def load():
            with connect('unused') as connection:
                with connection.cursor() as arbitrary:
                    stmt = sql.SQL('INSERT INTO {} VALUES %s').format(sql.Identifier(SCHEMA, TABLE))
                    batch(arbitrary, stmt, [])
                    arbitrary.copy_expert('COPY raw.copied FROM STDIN', None)
                    arbitrary.copy_expert('COPY raw.not_written TO STDOUT', None)
    """)
    assert targets(result) == {("raw", "Case Sensitive"), ("raw", "copied")}


@pytest.mark.parametrize("sql, expected", [
    ("SELECT 'INSERT INTO raw.fake VALUES (1)'", set()),
    ("-- INSERT INTO raw.fake VALUES (1)\nSELECT 1", set()),
    ("/* outer /* nested */ UPDATE raw.fake SET x=1 */ SELECT 1", set()),
    ("SELECT $$ DELETE FROM raw.fake $$", set()),
    ("COPY raw.read_only TO STDOUT", set()),
    ("COPY (SELECT * FROM raw.read_only) TO STDOUT", set()),
    ("COPY raw.loaded (a,b) FROM STDIN", {("raw", "loaded")}),
    ("WITH moved AS (DELETE FROM raw.source RETURNING *) INSERT INTO raw.dest SELECT * FROM moved", {("raw", "source"), ("raw", "dest")}),
    ("WITH a AS MATERIALIZED (SELECT 1), b AS (UPDATE raw.t SET x=1 RETURNING *) SELECT * FROM b", {("raw", "t")}),
    ('INSERT INTO "Raw Schema"."My Table" VALUES (1)', {("Raw Schema", "My Table")}),
    ('INSERT INTO RAW.PRICES VALUES (1)', {("raw", "prices")}),
    ('TRUNCATE TABLE raw.one, raw.two RESTART IDENTITY', {("raw", "one"), ("raw", "two")}),
    ("MERGE INTO raw.target USING raw.source ON TRUE WHEN MATCHED THEN UPDATE SET x=1", {("raw", "target")}),
    ("DELETE FROM raw.target; UPDATE raw.other SET x=2", {("raw", "target"), ("raw", "other")}),
])
def test_sql_lexer_extracts_only_executable_destinations(sql, expected):
    found, incomplete = sql_write_targets(sql)
    assert set(found) == expected
    assert not incomplete


def test_dynamic_identifiers_are_not_normalized_into_fake_tables(tmp_path):
    result = analyze(tmp_path, """
        def load(cursor, table, payload):
            cursor.execute(f'INSERT INTO raw.{table} VALUES (1)')
            cursor.execute(f'INSERT INTO raw.known VALUES ({payload})')
    """)
    assert targets(result) == {("raw", "known")}
    assert "WRITE_TARGET_UNKNOWN" in {d["code"] for d in result.diagnostics}


def test_dataclass_and_namedtuple_configuration_values(tmp_path):
    result = analyze(tmp_path, {
        "settings.py": """
            from dataclasses import dataclass, field
            from typing import NamedTuple
            @dataclass(frozen=True)
            class BaseSettings:
                schema: str = 'raw'
            @dataclass(frozen=True)
            class Settings(BaseSettings):
                table: str = field(default='default_name')
            class Target(NamedTuple):
                schema: str
                table: str
            CONFIG = Settings(table='overridden')
            SECOND = Target('curated', 'history')
        """,
        "loader.py": """
            from settings import CONFIG, SECOND
            def load(df):
                for config in (CONFIG, SECOND):
                    df.to_sql(config.table, schema=config.schema)
        """,
    })
    assert targets(result) == {("raw", "overridden"), ("curated", "history")}


def test_dataclass_default_factory_is_not_called_when_value_supplied(tmp_path):
    result = analyze(tmp_path, """
        from dataclasses import dataclass, field
        def factory():
            df.to_sql('wrong')
            return 'default'
        @dataclass
        class Config:
            table: str = field(default_factory=factory)
        def load(df):
            config = Config('selected')
            df.to_sql(config.table)
    """)
    assert targets(result) == {(None, "selected")}


def test_enum_values_can_hold_table_names_or_schema_table_tuples(tmp_path):
    result = analyze(tmp_path, """
        from enum import Enum
        class Targets(Enum):
            PRICE = ('raw', 'prices')
            HISTORY = ('curated', 'history')
        def load(df):
            for target in (Targets.PRICE, Targets.HISTORY):
                schema, table = target.value
                df.to_sql(table, schema=schema)
    """)
    assert targets(result) == {("raw", "prices"), ("curated", "history")}


def test_old_class_alias_retains_original_method_and_constants(tmp_path):
    result = analyze(tmp_path, """
        class Config:
            TABLE = 'old'
            @classmethod
            def table(cls): return cls.TABLE
        Original = Config
        class Config:
            TABLE = 'new'
            @classmethod
            def table(cls): return cls.TABLE
        def load(df):
            df.to_sql(Original.table())
            df.to_sql(Config.table())
    """)
    assert targets(result) == {(None, "old"), (None, "new")}


def test_none_is_not_a_dataframe(tmp_path):
    result = analyze(tmp_path, """
        def write(df=None): df.to_sql('wrong')
        def load(): write()
    """)
    assert not result.refs


def test_known_read_statements_and_query_updates(tmp_path):
    result = analyze(tmp_path, """
        from sqlalchemy import select, text
        from sqlalchemy.orm import Session
        class Model:
            __tablename__ = 'prices'
            __table_args__ = {'schema':'raw'}
        def load(s: Session):
            s.execute(select(Model).where(True))
            s.execute(text('SELECT 1'))
            s.execute(text('UPDATE raw.bound SET x=:value').bindparams(value=1))
            s.query(Model).filter(True).update({'value': 1})
    """)
    assert targets(result) == {("raw", "prices"), ("raw", "bound")}
    assert not result.diagnostics


def test_orm_instances_from_finite_comprehension(tmp_path):
    result = analyze(tmp_path, """
        from sqlalchemy.orm import Session
        class Model:
            __tablename__ = 'prices'
            __table_args__ = {'schema':'raw'}
        def load(db: Session):
            db.add_all([Model() for _ in (1,2)])
    """)
    assert targets(result) == {("raw", "prices")}


@pytest.mark.parametrize("body", [
    "config = {'table': 'wrong'}\nconfig.update(runtime)\ndf.to_sql(config['table'])",
    "config = {'table': 'wrong'}\nconfig[runtime] = 'changed'\ndf.to_sql(config['table'])",
    "config = {'table': 'wrong'}\nmutate(config)\ndf.to_sql(config.get('table'))",
    "df.to_sql(f'{runtime}'.replace('__PORTAL_UNKNOWN_VALUE__', 'wrong'))",
])
def test_unknown_mutations_cannot_resurrect_stale_targets(tmp_path, body):
    result = analyze(tmp_path, "def load(df, runtime):\n" + textwrap.indent(body, "    "))
    assert not result.refs


def test_known_local_dict_update_preserves_new_value(tmp_path):
    result = analyze(tmp_path, """
        def load(df):
            config = {'table':'old', 'schema':'raw'}
            config.update(table='new')
            df.to_sql(config['table'], schema=config['schema'])
    """)
    assert targets(result) == {("raw", "new")}


def test_global_configuration_mutation_cannot_reuse_source_default(tmp_path):
    result = analyze(tmp_path, """
        CONFIG = {'table':'old'}
        def load(df, runtime):
            alias = CONFIG
            alias.update(runtime)
            df.to_sql(CONFIG['table'])
    """)
    assert not result.refs


def test_class_override_mutation_cannot_reuse_base_value(tmp_path):
    result = analyze(tmp_path, """
        class Config:
            table = 'old'
        def load(df, runtime):
            Config.table = runtime
            df.to_sql(Config.table)
    """)
    assert not result.refs


def test_regular_package_does_not_mix_children_from_other_root(tmp_path):
    from domains.catalog.lineage_adapters.python_loader_analysis import PythonModuleRoots

    first, second = tmp_path / "first", tmp_path / "second"
    (first / "pkg").mkdir(parents=True)
    (second / "pkg").mkdir(parents=True)
    (first / "pkg" / "__init__.py").write_text("", encoding="utf-8")
    (second / "pkg" / "settings.py").write_text("TABLE='wrong'", encoding="utf-8")
    entry = first / "loader.py"
    entry.write_text("from pkg.settings import TABLE\ndef load(df): df.to_sql(TABLE)", encoding="utf-8")
    result = PythonLoaderAnalyzer(PythonModuleRoots([first, second])).analyze(entry, "load")
    assert not result.refs
    assert "MODULE_AMBIGUOUS" in {d["code"] for d in result.diagnostics}


def test_known_target_survives_independent_unknown_native_statement(tmp_path):
    result = analyze(tmp_path, """
        def load(cursor, dynamic):
            cursor.execute(f'{dynamic} INTO raw.wrong VALUES (1)')
            cursor.execute('INSERT INTO raw.confirmed VALUES (1)')
    """)
    assert targets(result) == {("raw", "confirmed")}
    assert "WRITE_TARGET_UNKNOWN" in {d["code"] for d in result.diagnostics}
