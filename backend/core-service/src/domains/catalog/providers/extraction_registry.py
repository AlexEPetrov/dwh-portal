from __future__ import annotations

from typing import Any

from domains.catalog.providers.lineage import ExtractionSourceRecord, LoaderMetadata
from domains.catalog.providers.python_metadata import resolve_python_metadata
from domains.catalog.providers.rest_metadata import resolve_rest_metadata
from settings.portal import DwhCollectorSettings


class ExtractionRegistryMissing(Exception):
    """Target DWH has no sys.data_extraction_sources table."""


def _is_undefined_table(exc: Exception) -> bool:
    if type(exc).__name__ == "UndefinedTable":
        return True
    return getattr(exc, "pgcode", None) == "42P01"


class ExtractionRegistryProvider:
    """Read sys.data_extraction_sources and resolve loader metadata contracts."""

    def __init__(self, settings: DwhCollectorSettings | None = None, connection: Any | None = None):
        self._settings = settings or DwhCollectorSettings()
        self._connection = connection

    def list_extraction_sources(self) -> list[ExtractionSourceRecord]:
        connection = self._connection or self._connect()
        should_close = self._connection is None
        try:
            return self._read_registry(connection)
        except ExtractionRegistryMissing:
            raise
        except Exception as exc:
            if _is_undefined_table(exc):
                raise ExtractionRegistryMissing(
                    "sys.data_extraction_sources is not present"
                ) from exc
            raise
        finally:
            if should_close:
                connection.close()

    def resolve_process_metadata(self, handler: dict[str, Any]) -> LoaderMetadata:
        handler_type = str(handler.get("handler_type") or "")
        name = str(handler.get("name") or handler.get("module") or handler_type or "loader")
        if handler_type in {"Python", "PythonV0"}:
            module_name = handler.get("module")
            if not module_name:
                return LoaderMetadata(
                    schema_version="1.0",
                    name=name,
                    metadata_status="MISSING",
                    diagnostic={"code": "MODULE_MISSING", "message": "Python handler has no module"},
                )
            return resolve_python_metadata(str(module_name), name)
        if handler_type == "RestApi":
            url_path = handler.get("url_path")
            if not url_path:
                return LoaderMetadata(
                    schema_version="1.0",
                    name=name,
                    metadata_status="MISSING",
                    diagnostic={"code": "URL_MISSING", "message": "RestApi handler has no url_path"},
                )
            return resolve_rest_metadata(str(url_path), name)
        return LoaderMetadata(
            schema_version="1.0",
            name=name,
            metadata_status="MISSING",
            diagnostic={"code": "UNSUPPORTED_HANDLER", "message": handler_type},
        )

    def _connect(self):
        from domains.catalog.providers.connection import connect_dwh_readonly

        return connect_dwh_readonly(self._settings)

    def _read_registry(self, connection) -> list[ExtractionSourceRecord]:
        # Live DWH columns drift between environments (descr vs description,
        # load_schedule_id vs schedule_id). Resolve against information_schema.
        columns = self._table_columns(connection, "sys", "data_extraction_sources")
        if not columns:
            raise ExtractionRegistryMissing("sys.data_extraction_sources is not present")
        descr_expr = self._first_existing(columns, "descr", "description")
        schedule_expr = self._first_existing(columns, "load_schedule_id", "schedule_id")
        access_expr = "s.access_level" if "access_level" in columns else "NULL"
        active_expr = "s.is_active" if "is_active" in columns else "TRUE"
        type_expr = (
            "s.extract_source_type_id" if "extract_source_type_id" in columns else "NULL"
        )
        tags_expr = "s.tags" if "tags" in columns else "NULL"
        comment_expr = "s.comment" if "comment" in columns else "NULL"
        ds_columns = self._table_columns(connection, "sys", "data_source_items")
        if ds_columns:
            ds_join = "LEFT JOIN sys.data_source_items d ON d.id = s.data_source_id"
            ds_name_expr = "COALESCE(d.name_eng, d.name_rus, d.slug)"
        else:
            ds_join = ""
            ds_name_expr = "NULL"
        with connection.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT
                    s.id,
                    s.name,
                    {descr_expr},
                    {access_expr},
                    {active_expr},
                    {type_expr},
                    s.extract_options,
                    s.storage_options,
                    s.load_options,
                    {schedule_expr},
                    s.data_source_id,
                    {ds_name_expr},
                    {tags_expr},
                    s.parent_id,
                    {comment_expr}
                FROM sys.data_extraction_sources s
                {ds_join}
                """
            )
            rows = cursor.fetchall()
        records = []
        for row in rows:
            records.append(
                ExtractionSourceRecord(
                    id=str(row[0]),
                    name=row[1],
                    descr=row[2],
                    access_level=row[3],
                    is_active=row[4] if row[4] is not None else True,
                    extract_source_type_id=row[5],
                    extract_options=row[6] or {},
                    storage_options=row[7] or {},
                    load_options=row[8] or {},
                    load_schedule_id=str(row[9]) if row[9] else None,
                    data_source_id=str(row[10]) if row[10] else None,
                    data_source_name=row[11],
                    tags=row[12],
                    parent_id=str(row[13]) if row[13] else None,
                    comment=row[14],
                )
            )
        return records

    @staticmethod
    def _table_columns(connection, schema: str, table: str) -> set[str]:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = %s AND table_name = %s
                """,
                (schema, table),
            )
            return {str(row[0]) for row in cursor.fetchall()}

    @staticmethod
    def _first_existing(columns: set[str], *names: str, table_alias: str = "s") -> str:
        for name in names:
            if name in columns:
                return f"{table_alias}.{name}"
        return "NULL"
