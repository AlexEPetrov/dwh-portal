import datetime
import uuid
from decimal import Decimal

from domains.catalog.models import Asset, AssetType
from domains.catalog.providers.log_files import LogFilesProvider
from domains.catalog.seed import PROVIDER_REG
from domains.catalog.services.extraction_load_service import ExtractionLoadService

SOURCE_ID = "c2000000-0000-0000-0000-000000000006"
TS_NEW = datetime.datetime(2026, 1, 3, tzinfo=datetime.timezone.utc)
TS_OLD = datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc)

LOG_COLUMNS = {
    "rid",
    "name",
    "timestamp",
    "status",
    "file_size",
    "checksum",
    "load_duration_sec",
    "doc_date_actual",
    "extraction_source_id",
}


class FakeCursor:
    def __init__(self, connection: "FakeConnection"):
        self._connection = connection
        self._rows: list[tuple] = []

    def __enter__(self) -> "FakeCursor":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False

    def execute(self, sql: str, params=None) -> None:
        normalized = " ".join(sql.lower().split())
        self._connection.executed.append((normalized, params))
        if "information_schema.columns" in normalized:
            schema, table = params
            if schema == "sys" and table == "log_files":
                self._rows = [(name,) for name in self._connection.columns]
            else:
                self._rows = []
            return
        if "count(*)" in normalized:
            source_id = str(params[0])
            self._rows = [
                (
                    sum(
                        1
                        for row in self._connection.rows
                        if str(row["extraction_source_id"]) == source_id
                    ),
                )
            ]
            return
        source_id = str(params[0])
        limit, offset = int(params[1]), int(params[2])
        matched = [
            row for row in self._connection.rows if str(row["extraction_source_id"]) == source_id
        ]
        matched.sort(key=lambda row: (row["timestamp"], row["rid"]), reverse=True)
        page_rows = matched[offset : offset + limit]
        select_part = sql.split("FROM", 1)[0].replace("SELECT", "", 1)
        idents = [part.strip().strip('"') for part in select_part.split(",") if part.strip()]
        self._rows = [tuple(row.get(ident) for ident in idents) for row in page_rows]

    def fetchall(self) -> list[tuple]:
        return list(self._rows)

    def fetchone(self) -> tuple:
        return self._rows[0] if self._rows else (0,)


class FakeConnection:
    def __init__(self, columns: set[str], rows: list[dict]):
        self.columns = columns
        self.rows = rows
        self.closed = False
        self.executed = []

    def cursor(self) -> FakeCursor:
        return FakeCursor(self)

    def close(self) -> None:
        self.closed = True


class ExplodingProvider:
    def list_files(self, extraction_source_id: str, page: int, page_size: int):
        raise AssertionError("must not query log_files")


def _file_row(name: str, loaded_at: datetime.datetime, rid: str) -> dict:
    return {
        "rid": uuid.UUID(rid),
        "name": name,
        "timestamp": loaded_at,
        "status": 1,
        "file_size": 500,
        "checksum": "abc",
        "load_duration_sec": Decimal("40"),
        "doc_date_actual": TS_OLD,
        "extraction_source_id": uuid.UUID(SOURCE_ID),
    }


def test_log_files_are_paged_newest_first():
    connection = FakeConnection(
        LOG_COLUMNS,
        [
            _file_row("old.xlsx", TS_OLD, "c2000000-0000-0000-0000-000000000001"),
            _file_row("new.xlsx", TS_NEW, "c2000000-0000-0000-0000-000000000002"),
            _file_row(
                "mid.xlsx",
                datetime.datetime(2026, 1, 2, tzinfo=datetime.timezone.utc),
                "c2000000-0000-0000-0000-000000000003",
            ),
        ],
    )
    provider = LogFilesProvider(connection=connection)
    page = provider.list_files(SOURCE_ID, page=1, page_size=2)
    assert page.available is True
    assert page.total == 3
    assert [item.file_name for item in page.items] == ["new.xlsx", "mid.xlsx"]
    assert page.items[0].load_duration_sec == 40.0
    second = provider.list_files(SOURCE_ID, page=2, page_size=2)
    assert [item.file_name for item in second.items] == ["old.xlsx"]


def test_missing_log_files_table_is_empty_unavailable():
    provider = LogFilesProvider(connection=FakeConnection(set(), []))
    page = provider.list_files(SOURCE_ID, page=1, page_size=50)
    assert page.available is False
    assert page.items == []
    assert page.total == 0


def test_fast_page_fetches_only_51_rows_and_never_counts():
    rows = [_file_row(f"file_{i}.xlsx", TS_NEW, str(uuid.UUID(int=i + 1))) for i in range(101)]
    other = _file_row("other_source.xlsx", TS_NEW, str(uuid.UUID(int=200)))
    other["extraction_source_id"] = uuid.uuid4()
    connection = FakeConnection(LOG_COLUMNS, [*rows, other])
    provider = LogFilesProvider(connection=connection)
    first = provider.list_files(SOURCE_ID, 1, 50, include_total=False)
    second = provider.list_files(SOURCE_ID, 2, 50, include_total=False)
    last = provider.list_files(SOURCE_ID, 3, 50, include_total=False)
    empty = provider.list_files(SOURCE_ID, 4, 50, include_total=False)
    assert first.total is None
    assert len(first.items) == len(second.items) == 50
    assert first.has_more is second.has_more is True
    assert len(last.items) == 1
    assert last.has_more is empty.has_more is False
    assert empty.items == []
    assert not ({item.id for item in first.items} & {item.id for item in second.items})
    assert first.items[0].file_name == "file_100.xlsx"
    assert not any("count(*)" in sql for sql, _ in connection.executed)
    reads = [(sql, params) for sql, params in connection.executed if "from sys.log_files" in sql]
    assert [params for _, params in reads] == [
        (SOURCE_ID, 51, 0),
        (SOURCE_ID, 51, 50),
        (SOURCE_ID, 51, 100),
        (SOURCE_ID, 51, 150),
    ]
    assert all('order by "timestamp" desc nulls last, "rid" desc' in sql for sql, _ in reads)


def test_unconfigured_dwh_is_empty_unavailable():
    from settings.portal import DwhCollectorSettings

    settings = DwhCollectorSettings.model_construct(psg_host=None, psg_db=None)
    provider = LogFilesProvider(settings=settings)
    page = provider.list_files(SOURCE_ID, page=1, page_size=50)
    assert page.available is False
    assert page.items == []


def test_registry_extraction_reads_provider(store):
    asset = store.upsert_asset(
        Asset(
            asset_type=AssetType.EXTRACTION_SOURCE,
            qualified_name="extraction:src",
            name="src",
            identity_key="extraction:src",
            source_provider=PROVIDER_REG,
            native_id=SOURCE_ID,
            first_seen_at=TS_NEW,
            last_seen_at=TS_NEW,
        )
    )
    connection = FakeConnection(
        LOG_COLUMNS,
        [_file_row("document_1.xlsx", TS_NEW, "c2000000-0000-0000-0000-000000000999")],
    )
    service = ExtractionLoadService(store, LogFilesProvider(connection=connection))
    page = service.list_loads(asset.id, 1, 50)
    assert page is not None
    assert page.available is True
    assert page.items[0].file_name == "document_1.xlsx"


def test_airflow_extraction_does_not_query_log_files(store):
    asset = store.upsert_asset(
        Asset(
            asset_type=AssetType.EXTRACTION_SOURCE,
            qualified_name="extraction:dag",
            name="dag",
            identity_key="extraction:dag",
            source_provider="airflow_dags",
            native_id=SOURCE_ID,
            first_seen_at=TS_NEW,
            last_seen_at=TS_NEW,
        )
    )
    service = ExtractionLoadService(store, ExplodingProvider())  # type: ignore[arg-type]
    page = service.list_loads(asset.id, 1, 50)
    assert page is not None
    assert page.available is False
    assert page.items == []


def test_owned_connection_reuses_nonempty_column_cache(monkeypatch):
    from domains.catalog.providers import log_files as module
    from settings.portal import DwhCollectorSettings

    module._COLUMN_CACHE.clear()
    connection = FakeConnection(set(LOG_COLUMNS), [])
    calls = {"schema": 0}
    original = FakeCursor.execute

    def execute(self, sql, params=None):
        if "information_schema.columns" in " ".join(sql.lower().split()):
            calls["schema"] += 1
        return original(self, sql, params)

    monkeypatch.setattr(FakeCursor, "execute", execute)
    settings = DwhCollectorSettings.model_construct(
        psg_host="cache-host", psg_port=5432, psg_db="cache-db"
    )
    provider = LogFilesProvider(settings=settings)
    monkeypatch.setattr(provider, "_connect", lambda: connection)
    try:
        provider.list_files(SOURCE_ID, page=1, page_size=10)
        provider.list_files(SOURCE_ID, page=1, page_size=10)
        assert calls["schema"] == 1
    finally:
        module._COLUMN_CACHE.clear()


def test_empty_column_probe_is_not_cached(monkeypatch):
    from domains.catalog.providers import log_files as module
    from settings.portal import DwhCollectorSettings

    module._COLUMN_CACHE.clear()
    connection = FakeConnection(set(), [])
    calls = {"schema": 0}
    original = FakeCursor.execute

    def execute(self, sql, params=None):
        if "information_schema.columns" in " ".join(sql.lower().split()):
            calls["schema"] += 1
        return original(self, sql, params)

    monkeypatch.setattr(FakeCursor, "execute", execute)
    settings = DwhCollectorSettings.model_construct(
        psg_host="empty-host", psg_port=5432, psg_db="empty-db"
    )
    provider = LogFilesProvider(settings=settings)
    monkeypatch.setattr(provider, "_connect", lambda: connection)
    try:
        assert provider.list_files(SOURCE_ID, page=1, page_size=10).available is False
        connection.columns = set(LOG_COLUMNS)
        connection.rows = [_file_row("later.xlsx", TS_NEW, "c2000000-0000-0000-0000-000000000004")]
        page = provider.list_files(SOURCE_ID, page=1, page_size=10)
        assert calls["schema"] == 2
        assert page.available is True
        assert page.items[0].file_name == "later.xlsx"
    finally:
        module._COLUMN_CACHE.clear()


def test_injected_connection_ignores_column_cache():
    from domains.catalog.providers import log_files as module
    from settings.portal import DwhCollectorSettings

    module._COLUMN_CACHE[("h", 5432, "d", "sys", "log_files")] = frozenset({"rid"})
    try:
        connection = FakeConnection(
            LOG_COLUMNS,
            [_file_row("kept.xlsx", TS_NEW, "c2000000-0000-0000-0000-000000000005")],
        )
        provider = LogFilesProvider(
            settings=DwhCollectorSettings.model_construct(psg_host="h", psg_port=5432, psg_db="d"),
            connection=connection,
        )
        page = provider.list_files(SOURCE_ID, page=1, page_size=10)
        assert page.available is True
        assert page.items[0].file_name == "kept.xlsx"
    finally:
        module._COLUMN_CACHE.clear()


def test_unknown_asset_returns_none(store):
    service = ExtractionLoadService(store, ExplodingProvider())  # type: ignore[arg-type]
    assert service.list_loads(uuid.uuid4(), 1, 50) is None
