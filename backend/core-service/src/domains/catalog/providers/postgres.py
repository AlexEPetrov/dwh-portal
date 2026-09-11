from __future__ import annotations

from typing import Any

from domains.catalog.models import AssetType
from domains.catalog.providers.metadata import CatalogObject
from settings.portal import DwhCollectorSettings

RELATION_KIND = {
    "r": AssetType.TABLE,
    "v": AssetType.VIEW,
    "m": AssetType.MATERIALIZED_VIEW,
}


class DirectPostgresMetadataProvider:
    """Read-only PostgreSQL catalog provider. Does not run COUNT(*)."""

    def __init__(self, settings: DwhCollectorSettings | None = None, connection: Any | None = None):
        self._settings = settings or DwhCollectorSettings()
        self._connection = connection

    def list_assets(self) -> list[CatalogObject]:
        connection = self._connection or self._connect()
        should_close = self._connection is None
        try:
            return self._read_catalog(connection)
        finally:
            if should_close:
                connection.close()

    def get_asset(self, qualified_name: str) -> CatalogObject | None:
        for item in self.list_assets():
            current = ".".join(part for part in [item.database, item.schema, item.name] if part)
            if current == qualified_name:
                return item
        return None

    def _connect(self):
        import psycopg2

        if not self._settings.psg_host or not self._settings.psg_db:
            raise RuntimeError("DWH collector connection is not configured")
        return psycopg2.connect(
            host=self._settings.psg_host,
            port=self._settings.psg_port,
            user=self._settings.psg_user,
            password=self._settings.psg_pass,
            dbname=self._settings.psg_db,
        )

    def _read_catalog(self, connection) -> list[CatalogObject]:
        database = self._settings.psg_db or "dwh"
        objects: list[CatalogObject] = [
            CatalogObject(asset_type=AssetType.DATABASE, database=database, schema=None, name=database)
        ]
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT n.oid, n.nspname, obj_description(n.oid, 'pg_namespace')
                FROM pg_namespace n
                WHERE n.nspname NOT LIKE 'pg_%'
                  AND n.nspname <> 'information_schema'
                ORDER BY n.nspname
                """
            )
            schemas = cursor.fetchall()
            for oid, name, description in schemas:
                objects.append(
                    CatalogObject(
                        asset_type=AssetType.SCHEMA,
                        database=database,
                        schema=name,
                        name=name,
                        description=description,
                        native_id=str(oid),
                    )
                )

            cursor.execute(
                """
                SELECT
                    c.oid,
                    n.nspname,
                    c.relname,
                    c.relkind,
                    obj_description(c.oid, 'pg_class'),
                    pg_relation_size(c.oid),
                    pg_indexes_size(c.oid),
                    pg_total_relation_size(c.oid),
                    c.reltuples
                FROM pg_class c
                JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE c.relkind IN ('r', 'v', 'm')
                  AND n.nspname NOT LIKE 'pg_%'
                  AND n.nspname <> 'information_schema'
                ORDER BY n.nspname, c.relname
                """
            )
            relations = cursor.fetchall()
            cursor.execute(
                """
                SELECT
                    c.oid,
                    a.attnum,
                    a.attname,
                    pg_catalog.format_type(a.atttypid, a.atttypmod),
                    NOT a.attnotnull,
                    col_description(c.oid, a.attnum)
                FROM pg_attribute a
                JOIN pg_class c ON c.oid = a.attrelid
                JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE a.attnum > 0
                  AND NOT a.attisdropped
                  AND c.relkind IN ('r', 'v', 'm')
                  AND n.nspname NOT LIKE 'pg_%'
                  AND n.nspname <> 'information_schema'
                ORDER BY c.oid, a.attnum
                """
            )
            columns_by_oid: dict[str, list[dict[str, Any]]] = {}
            for oid, attnum, attname, data_type, nullable, description in cursor.fetchall():
                columns_by_oid.setdefault(str(oid), []).append(
                    {
                        "ordinal": attnum,
                        "name": attname,
                        "data_type": data_type,
                        "nullable": nullable,
                        "description": description,
                    }
                )

        for oid, schema, name, relkind, description, table_bytes, index_bytes, total_bytes, reltuples in relations:
            asset_type = RELATION_KIND.get(relkind)
            if asset_type is None:
                continue
            objects.append(
                CatalogObject(
                    asset_type=asset_type,
                    database=database,
                    schema=schema,
                    name=name,
                    description=description,
                    native_id=str(oid),
                    columns=columns_by_oid.get(str(oid), []),
                    table_bytes=int(table_bytes) if table_bytes is not None else None,
                    index_bytes=int(index_bytes) if index_bytes is not None else None,
                    total_bytes=int(total_bytes) if total_bytes is not None else None,
                    row_estimate=int(reltuples) if reltuples is not None and reltuples >= 0 else None,
                )
            )
        return objects
