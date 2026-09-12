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
                (sum(1 for row in self._connection.rows if str(row["extraction_source_id"]) == source_id),)
            ]
            return
        source_id = str(params[0])
        limit, offset = int(params[1]), int(params[2])
        matched = [row for row in self._connection.rows if str(row["extraction_source_id"]) == source_id]
        matched.sort(key=lambda row: row["timestamp"] or datetime.datetime.min, reverse=True)
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
            _file_row("mid.xlsx", datetime.datetime(2026, 1, 2, tzinfo=datetime.timezone.utc), "c2000000-0000-0000-0000-000000000003"),
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
    connection = FakeConnection(LOG_COLUMNS, [_file_row("document_1.xlsx", TS_NEW, "c2000000-0000-0000-0000-000000000999")])
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


def test_unknown_asset_returns_none(store):
    service = ExtractionLoadService(store, ExplodingProvider())  # type: ignore[arg-type]
    assert service.list_loads(uuid.uuid4(), 1, 50) is None
