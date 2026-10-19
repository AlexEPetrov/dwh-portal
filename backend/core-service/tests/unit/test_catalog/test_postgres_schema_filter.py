import pytest

from domains.catalog.providers.postgres import DirectPostgresMetadataProvider


class _Cursor:
    def __init__(self, connection: "_Connection"):
        self._connection = connection
        self._rows: list = []

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, sql, params=None):
        self._connection.statements.append((sql, params))
        self._rows = self._connection.rows_for(sql)

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def fetchall(self):
        return list(self._rows)


class _Connection:
    def __init__(self, schema_rows):
        self.schema_rows = schema_rows
        self.statements: list[tuple[str, object]] = []

    def cursor(self):
        return _Cursor(self)

    def close(self):
        return None

    def rows_for(self, sql: str):
        if "pg_namespace" in sql and "pg_class" not in sql and "pg_depend" not in sql:
            return self.schema_rows
        return []


def test_schema_allow_list_limits_size_and_column_queries():
    connection = _Connection(
        [
            (1, "raw", None),
            (2, "core", None),
            (3, "mart", None),
        ]
    )
    provider = DirectPostgresMetadataProvider(connection=connection, schemas=("raw", "core"))
    objects = provider.list_assets()
    names = [item.name for item in objects if item.asset_type.value == "SCHEMA"]
    assert names == ["raw", "core"]
    filtered = [sql for sql, params in connection.statements if params is not None]
    assert len(filtered) == 2
    assert all("pg_relation_size" in sql or "pg_attribute" in sql for sql in filtered)
    assert all(params == (["raw", "core"],) for _sql, params in connection.statements if params)
    assert all("mart" not in sql for sql, _params in connection.statements)
    for sql, params in connection.statements:
        if params is None:
            continue
        assert "LIKE 'pg_%%'" in sql
        assert "%" not in sql.replace("%%", "").replace("%s", "")


def test_missing_schema_fails_before_relation_size_query():
    connection = _Connection([(1, "raw", None)])
    provider = DirectPostgresMetadataProvider(connection=connection, schemas=("raw", "missing"))
    with pytest.raises(ValueError, match="schemas not found: missing"):
        provider.list_assets()
    assert not any("pg_relation_size" in sql for sql, _params in connection.statements)


def test_dependency_query_filters_dependent_schema():
    connection = _Connection([])
    provider = DirectPostgresMetadataProvider(connection=connection, schemas=("raw",))
    assert provider.list_relation_dependencies() == []
    sql, params = connection.statements[-1]
    assert "dependent_ns.nspname = ANY(%s)" in sql
    assert "LIKE 'pg_%%'" in sql
    assert "%" not in sql.replace("%%", "").replace("%s", "")
    assert params == (["raw"],)
