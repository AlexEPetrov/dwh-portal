from __future__ import annotations

import datetime
import re
from dataclasses import dataclass, replace
from decimal import Decimal
from typing import Any

from settings.portal import DwhCollectorSettings

_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

# Map API/service fields to possible DWH column names (first match wins).
_FIELD_CANDIDATES: dict[str, tuple[str, ...]] = {
    "id": ("rid", "id"),
    "file_name": ("name", "file_name", "filename", "path"),
    "loaded_at": ("timestamp", "loaded_at", "load_time", "created_at"),
    "status": ("status",),
    "file_size": ("file_size", "size_bytes", "size"),
    "checksum": ("checksum",),
    "load_duration_sec": ("load_duration_sec",),
    "doc_date_actual": ("doc_date_actual",),
}
_SOURCE_ID_CANDIDATES = ("extraction_source_id", "source_id")

# Non-empty column sets for connections this process opens itself.
# An injected connection is not cached: tests and callers can swap schemas.
_COLUMN_CACHE: dict[tuple[str | None, int, str | None, str, str], frozenset[str]] = {}


def _is_undefined_table(exc: Exception) -> bool:
    if type(exc).__name__ == "UndefinedTable":
        return True
    return getattr(exc, "pgcode", None) == "42P01"


def _quote_ident(name: str) -> str:
    if not _IDENT.fullmatch(name):
        raise ValueError(f"unsafe identifier: {name!r}")
    return f'"{name}"'


@dataclass(frozen=True)
class LoadFileRecord:
    """One row from sys.log_files after canonical field mapping."""

    id: str
    file_name: str
    loaded_at: datetime.datetime | None = None
    status: int | None = None
    file_size: int | None = None
    checksum: str | None = None
    load_duration_sec: float | None = None
    doc_date_actual: datetime.datetime | None = None
    database: str | None = None
    extraction_source_id: str | None = None


@dataclass(frozen=True)
class LoadFilePage:
    """Paged live read of extraction load files."""

    items: list[LoadFileRecord]
    total: int | None
    available: bool
    has_more: bool = False


class LogFilesProvider:
    """Read sys.log_files for a registry extraction source.

    Missing table or unconfigured DWH yields an empty unavailable page,
    not an exception. Callers MUST NOT treat this as catalog collection.
    """

    def __init__(self, settings: DwhCollectorSettings | None = None, connection: Any | None = None):
        self._settings = settings or DwhCollectorSettings()
        self._connection = connection

    def list_files(
        self, extraction_source_id: str, page: int, page_size: int, *, include_total: bool = True
    ) -> LoadFilePage:
        """Return newest files, optionally without counting the complete source history."""
        return self._list_files(extraction_source_id, page, page_size, include_total)

    def list_recent_files(self, limit: int) -> LoadFilePage:
        """Read the latest entries across all sources in the configured DWH in one query."""
        return self._list_files(None, 1, limit, False)

    def _list_files(
        self, extraction_source_id: str | None, page: int, page_size: int, include_total: bool
    ) -> LoadFilePage:
        if self._connection is None and (not self._settings.psg_host or not self._settings.psg_db):
            return LoadFilePage(items=[], total=0, available=False)
        connection = self._connection or self._connect()
        should_close = self._connection is None
        try:
            return self._read_page(connection, extraction_source_id, page, page_size, include_total)
        except Exception as exc:
            if _is_undefined_table(exc):
                return LoadFilePage(items=[], total=0, available=False)
            raise
        finally:
            if should_close:
                connection.close()

    def _connect(self):
        from domains.catalog.providers.connection import connect_dwh_readonly

        return connect_dwh_readonly(self._settings)

    def _read_page(
        self,
        connection,
        extraction_source_id: str | None,
        page: int,
        page_size: int,
        include_total: bool,
    ) -> LoadFilePage:
        columns = self._table_columns(connection, "sys", "log_files")
        source_col = next((name for name in _SOURCE_ID_CANDIDATES if name in columns), None)
        if not columns or source_col is None:
            return LoadFilePage(items=[], total=0, available=False)
        selected: list[tuple[str, str]] = []
        for field, candidates in _FIELD_CANDIDATES.items():
            col = next((name for name in candidates if name in columns), None)
            if col is not None:
                selected.append((field, _quote_ident(col)))
        if not selected:
            return LoadFilePage(items=[], total=0, available=False)
        source_ident = _quote_ident(source_col)
        if extraction_source_id is None:
            selected.append(("extraction_source_id", source_ident))
        time_ident = next((ident for field, ident in selected if field == "loaded_at"), None)
        # Without a timestamp the global panel cannot truthfully claim these are recent loads.
        if extraction_source_id is None and time_ident is None:
            return LoadFilePage(items=[], total=0, available=False)
        order_ident = time_ident or next(
            (ident for field, ident in selected if field == "id"), source_ident
        )
        id_ident = next((ident for field, ident in selected if field == "id"), None)
        order_sql = f"{order_ident} DESC NULLS LAST"
        if id_ident is not None and id_ident != order_ident:
            order_sql += f", {id_ident} DESC"
        select_sql = ", ".join(ident for _, ident in selected)
        offset = max(page - 1, 0) * page_size
        total = None
        where_sql = f"WHERE {source_ident} = %s" if extraction_source_id is not None else ""
        source_params = (extraction_source_id,) if extraction_source_id is not None else ()
        with connection.cursor() as cursor:
            if include_total:
                cursor.execute(
                    f"SELECT COUNT(*) FROM sys.log_files WHERE {source_ident} = %s",
                    (extraction_source_id,),
                )
                total = int(cursor.fetchone()[0] or 0)
            cursor.execute(
                f"""
                SELECT {select_sql}
                FROM sys.log_files
                {where_sql}
                ORDER BY {order_sql}
                LIMIT %s OFFSET %s
                """,
                (*source_params, page_size if include_total else page_size + 1, offset),
            )
            rows = cursor.fetchall()
            has_more = offset + page_size < total if total is not None else len(rows) > page_size
            items = [
                replace(self._record(selected, row), database=self._settings.psg_db)
                for row in rows[:page_size]
            ]
        return LoadFilePage(items=items, total=total, available=True, has_more=has_more)

    @staticmethod
    def _record(selected: list[tuple[str, str]], row: tuple[Any, ...]) -> LoadFileRecord:
        values: dict[str, Any] = {
            field: value for (field, _), value in zip(selected, row, strict=True)
        }
        loaded_at = values.get("loaded_at")
        doc_date = values.get("doc_date_actual")
        status = values.get("status")
        file_size = values.get("file_size")
        duration = values.get("load_duration_sec")
        raw_id = values.get("id")
        raw_name = values.get("file_name")
        return LoadFileRecord(
            id="" if raw_id is None else str(raw_id),
            file_name="" if raw_name is None else str(raw_name),
            loaded_at=loaded_at if isinstance(loaded_at, datetime.datetime) else None,
            status=int(status) if status is not None else None,
            file_size=int(file_size) if file_size is not None else None,
            checksum=None if values.get("checksum") is None else str(values.get("checksum")),
            load_duration_sec=_as_float(duration),
            doc_date_actual=doc_date if isinstance(doc_date, datetime.datetime) else None,
            extraction_source_id=(
                str(values["extraction_source_id"])
                if values.get("extraction_source_id") is not None
                else None
            ),
        )

    def _table_columns(self, connection, schema: str, table: str) -> set[str]:
        cache_key = self._column_cache_key(schema, table)
        if cache_key is not None:
            cached = _COLUMN_CACHE.get(cache_key)
            if cached is not None:
                return set(cached)
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = %s AND table_name = %s
                """,
                (schema, table),
            )
            columns = {str(row[0]) for row in cursor.fetchall()}
        if cache_key is not None and columns:
            _COLUMN_CACHE[cache_key] = frozenset(columns)
        return columns

    def _column_cache_key(
        self, schema: str, table: str
    ) -> tuple[str | None, int, str | None, str, str] | None:
        if self._connection is not None:
            return None
        return (
            self._settings.psg_host,
            self._settings.psg_port,
            self._settings.psg_db,
            schema,
            table,
        )


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return float(value)
    return float(value)
