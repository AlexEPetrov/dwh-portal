from __future__ import annotations

import datetime
import uuid

from domains.catalog.identity import (
    compute_structure_hash,
    database_identity,
    relation_identity,
    schema_identity,
)
from domains.catalog.models import (
    Asset,
    AssetColumn,
    AssetSnapshot,
    AssetType,
    CollectionRun,
    CollectorStatus,
    Relationship,
    RelationshipType,
)
from domains.catalog.providers.metadata import CatalogObject, MetadataProvider
from domains.catalog.repositories.ports import PortalStore
from settings.portal import DwhCollectorSettings

PROVIDER = "postgres"
RELATION_TYPES = {AssetType.TABLE, AssetType.VIEW, AssetType.MATERIALIZED_VIEW}


class CatalogCollector:
    """Persist PostgreSQL catalog inventory as canonical assets."""

    def __init__(
        self,
        store: PortalStore,
        provider: MetadataProvider,
        settings: DwhCollectorSettings | None = None,
    ):
        self._store = store
        self._provider = provider
        self._settings = settings or DwhCollectorSettings()

    def run(self, now: datetime.datetime | None = None) -> CollectionRun:
        started = now or datetime.datetime.now(datetime.timezone.utc)
        seen: set[uuid.UUID] = set()
        counts = {"assets": 0, "columns": 0}
        try:
            objects = self._provider.list_assets()
            parents: dict[tuple[str, str | None], uuid.UUID] = {}
            for item in objects:
                asset = self._upsert(item, started)
                seen.add(asset.id)
                counts["assets"] += 1
                if item.asset_type == AssetType.DATABASE:
                    parents[(item.database, None)] = asset.id
                elif item.asset_type == AssetType.SCHEMA:
                    parents[(item.database, item.name)] = asset.id
                    db_id = parents.get((item.database, None))
                    if db_id:
                        self._contains(db_id, asset.id)
                elif item.asset_type in RELATION_TYPES:
                    schema_id = parents.get((item.database, item.schema))
                    if schema_id:
                        self._contains(schema_id, asset.id)
                    columns = [
                        AssetColumn(
                            asset_id=asset.id,
                            ordinal=int(column["ordinal"]),
                            name=column["name"],
                            data_type=column["data_type"],
                            nullable=bool(column.get("nullable", True)),
                            description=column.get("description"),
                        )
                        for column in item.columns
                    ]
                    self._store.replace_columns(asset.id, columns)
                    counts["columns"] += len(columns)
                    self._store.add_snapshot(
                        AssetSnapshot(
                            asset_id=asset.id,
                            snapshot_at=started,
                            table_bytes=item.table_bytes,
                            index_bytes=item.index_bytes,
                            total_bytes=item.total_bytes,
                            row_estimate=item.row_estimate,
                            structure_hash=compute_structure_hash(item.asset_type, columns, item.constraints),
                        )
                    )
            removed = self._store.mark_missing_as_deleted(
                PROVIDER,
                seen,
                started,
                asset_types={item.value for item in RELATION_TYPES | {AssetType.SCHEMA, AssetType.DATABASE}},
            )
            status = CollectorStatus.SUCCESS
            message = f"Collected {counts['assets']} assets"
            if removed:
                message = f"{message}, soft-deleted {len(removed)}"
        except Exception as exc:
            status = CollectorStatus.FAILED
            message = str(exc)
            counts["error"] = str(exc)
        finished = datetime.datetime.now(datetime.timezone.utc)
        run = CollectionRun(
            collector_name="catalog",
            started_at=started,
            finished_at=finished,
            status=status,
            message=message,
            details=counts,
        )
        return self._store.add_collection_run(run)

    def _upsert(self, item: CatalogObject, now: datetime.datetime) -> Asset:
        connection = self._settings.connection_identity
        if item.asset_type == AssetType.DATABASE:
            qualified_name, identity_key = database_identity(connection, item.database)
            attributes = {"database": item.database, "connection_identity": connection}
        elif item.asset_type == AssetType.SCHEMA:
            qualified_name, identity_key = schema_identity(connection, item.database, item.name)
            attributes = {"database": item.database, "schema": item.name}
        else:
            qualified_name, identity_key = relation_identity(
                connection, item.database, item.schema or "public", item.name
            )
            attributes = {
                "database": item.database,
                "schema": item.schema,
                "display_name": f"{item.schema}.{item.name}",
            }
        return self._store.upsert_asset(
            Asset(
                asset_type=item.asset_type,
                qualified_name=qualified_name,
                name=item.name,
                description=item.description,
                source_provider=PROVIDER,
                native_id=item.native_id,
                identity_key=identity_key,
                first_seen_at=now,
                last_seen_at=now,
                deleted_at=None,
                attributes=attributes,
            )
        )

    def _contains(self, parent_id: uuid.UUID, child_id: uuid.UUID) -> None:
        self._store.upsert_relationship(
            Relationship(
                from_asset_id=parent_id,
                to_asset_id=child_id,
                relationship_type=RelationshipType.CONTAINS,
                source_provider=PROVIDER,
            )
        )
