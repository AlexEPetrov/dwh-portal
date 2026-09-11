from __future__ import annotations

import datetime
import uuid

from domains.catalog.identity import (
    data_source_identity,
    extraction_source_identity,
    process_identity,
    relation_identity,
    storage_location_identity,
    strip_secrets,
    unresolved_target_identity,
)
from domains.catalog.models import (
    Asset,
    AssetType,
    CollectionRun,
    CollectorStatus,
    DiscoveryDiagnostic,
    LineageStatus,
    MetadataStatus,
    Relationship,
    RelationshipType,
)
from domains.catalog.providers.lineage import (
    STORAGE_TARGET_TYPES,
    VIEW_TARGET_TYPES,
    WRITE_RELATION_TYPES,
    ExtractionSourceRecord,
    LoaderMetadata,
    LineageProvider,
    LoaderTarget,
)
from domains.catalog.repositories.ports import PortalStore
from settings.portal import DwhCollectorSettings

PROVIDER = "extraction_registry"


def _is_derived_view_target(target: LoaderTarget) -> bool:
    """Views are not PROCESS write targets; they DERIVED_FROM a base table."""
    return str(target.type).lower() in VIEW_TARGET_TYPES


def _is_storage_write_target(target: LoaderTarget) -> bool:
    """PROCESS may WRITES_TO S3 / file / object-store locations."""
    return str(target.type).lower() in STORAGE_TARGET_TYPES


class ExtractionRegistryCollector:
    """Materialize source-to-DWH lineage without failing the whole catalog."""

    def __init__(
        self,
        store: PortalStore,
        provider: LineageProvider,
        settings: DwhCollectorSettings | None = None,
    ):
        self._store = store
        self._provider = provider
        self._settings = settings or DwhCollectorSettings()

    def run(self, now: datetime.datetime | None = None) -> CollectionRun:
        started = now or datetime.datetime.now(datetime.timezone.utc)
        details = {"sources": 0, "diagnostics": 0, "unresolved": 0}
        status = CollectorStatus.SUCCESS
        try:
            records = self._provider.list_extraction_sources()
            for record in records:
                self._ingest_record(record, started, details)
                details["sources"] += 1
            if details["diagnostics"] and details["sources"]:
                status = CollectorStatus.PARTIAL
            message = f"Ingested {details['sources']} extraction sources"
        except Exception as exc:
            status = CollectorStatus.FAILED
            message = str(exc)
            details["error"] = str(exc)
        run = CollectionRun(
            collector_name="extraction_registry",
            started_at=started,
            finished_at=datetime.datetime.now(datetime.timezone.utc),
            status=status,
            message=message,
            details=details,
        )
        return self._store.add_collection_run(run)

    def _ingest_record(
        self, record: ExtractionSourceRecord, now: datetime.datetime, details: dict
    ) -> None:
        extraction = self._upsert_extraction(record, now)
        if record.data_source_id:
            source = self._upsert_data_source(record, now)
            self._rel(source.id, extraction.id, RelationshipType.EXTRACTS_TO)
        storage = None
        if record.storage_options:
            storage = self._upsert_storage(record, now)
            self._rel(extraction.id, storage.id, RelationshipType.EXTRACTS_TO)
        if record.parent_id:
            parent_qn, parent_key = extraction_source_identity(record.parent_id)
            parent = self._store.find_by_identity(PROVIDER, parent_key)
            if parent is None:
                parent = self._store.upsert_asset(
                    Asset(
                        asset_type=AssetType.EXTRACTION_SOURCE,
                        qualified_name=parent_qn,
                        name=record.parent_id,
                        source_provider=PROVIDER,
                        native_id=record.parent_id,
                        identity_key=parent_key,
                        first_seen_at=now,
                        last_seen_at=now,
                    )
                )
            self._rel(parent.id, extraction.id, RelationshipType.PARENT_OF)

        handlers = list((record.load_options or {}).get("handlers") or [])
        for index, handler in enumerate(handlers):
            if not isinstance(handler, dict):
                continue
            handler_key = str(handler.get("name") or handler.get("module") or index)
            process = self._upsert_process(record, handler, handler_key, now)
            if storage is not None:
                self._rel(process.id, storage.id, RelationshipType.READS_FROM)
            metadata = self._provider.resolve_process_metadata(handler)
            self._apply_metadata(process, metadata, now, details)

    def _apply_metadata(
        self,
        process: Asset,
        metadata: LoaderMetadata,
        now: datetime.datetime,
        details: dict,
    ) -> None:
        attributes = dict(process.attributes)
        attributes["metadata_status"] = metadata.metadata_status
        attributes["handler_name"] = metadata.name
        if metadata.metadata_status != MetadataStatus.OK:
            attributes["lineage_status"] = LineageStatus.UNRESOLVED
            process.attributes = attributes
            self._store.upsert_asset(process)
            self._diagnostic(
                process.id,
                now,
                metadata.diagnostic or {"code": metadata.metadata_status, "message": metadata.metadata_status},
            )
            details["diagnostics"] += 1
            return

        unresolved = 0
        write_targets = [t for t in metadata.writes_to if not _is_derived_view_target(t)]
        derived_targets = [t for t in metadata.writes_to if _is_derived_view_target(t)]
        for target in write_targets:
            if _is_storage_write_target(target):
                dest = self._resolve_storage_write_target(target, process.id, now, details)
            else:
                dest = self._resolve_relation_write_target(target, process.id, now, details)
            if dest.attributes.get("unresolved"):
                unresolved += 1
            self._rel(process.id, dest.id, RelationshipType.WRITES_TO)
        for target in derived_targets:
            if target.derived_from is None:
                self._diagnostic(
                    process.id,
                    now,
                    {
                        "code": "VIEW_DERIVED_FROM_MISSING",
                        "message": (
                            f"{target.database}.{target.schema}.{target.name} is a view; "
                            "set derived_from to the base table (PROCESS must not WRITES_TO a view)"
                        ),
                        "target_ref": {
                            "type": target.type,
                            "database": target.database,
                            "schema": target.schema,
                            "name": target.name,
                        },
                    },
                )
                details["diagnostics"] += 1
                unresolved += 1
                continue
            view_asset = self._resolve_relation_target(target, process.id, now, details)
            base_asset = self._resolve_relation_target(target.derived_from, process.id, now, details)
            if view_asset.attributes.get("unresolved") or base_asset.attributes.get("unresolved"):
                unresolved += 1
            # VIEW DERIVED_FROM → TABLE
            self._rel(view_asset.id, base_asset.id, RelationshipType.DERIVED_FROM)
        attributes["lineage_status"] = (
            LineageStatus.UNRESOLVED
            if unresolved and not metadata.writes_to
            else LineageStatus.PARTIAL
            if unresolved
            else LineageStatus.RESOLVED
        )
        if not write_targets:
            attributes["lineage_status"] = LineageStatus.UNRESOLVED
        process.attributes = attributes
        self._store.upsert_asset(process)

    def _resolve_storage_write_target(
        self,
        target: LoaderTarget,
        process_id: uuid.UUID,
        now: datetime.datetime,
        details: dict,
    ) -> Asset:
        path = (target.path or target.name or "").strip()
        if not path:
            details["unresolved"] += 1
            details["diagnostics"] += 1
            self._diagnostic(
                process_id,
                now,
                {
                    "code": "TARGET_UNRESOLVED",
                    "message": "storage writes_to target requires path",
                    "target_ref": {"type": target.type},
                },
            )
            return self._unresolved_storage_target(target.type, now)
        qualified_name, identity_key = storage_location_identity(path)
        existing = self._store.find_by_identity(PROVIDER, identity_key)
        if existing is not None:
            existing.last_seen_at = now
            existing.deleted_at = None
            attrs = dict(existing.attributes or {})
            attrs["storage_kind"] = target.type
            attrs["path"] = path
            existing.attributes = attrs
            return self._store.upsert_asset(existing)
        return self._store.upsert_asset(
            Asset(
                asset_type=AssetType.STORAGE_LOCATION,
                qualified_name=qualified_name,
                name=path,
                source_provider=PROVIDER,
                identity_key=identity_key,
                first_seen_at=now,
                last_seen_at=now,
                attributes={"path": path, "storage_kind": target.type},
            )
        )

    def _resolve_relation_write_target(
        self,
        target: LoaderTarget,
        process_id: uuid.UUID,
        now: datetime.datetime,
        details: dict,
    ) -> Asset:
        kind = str(target.type).lower() or "table"
        if kind not in WRITE_RELATION_TYPES:
            # Unknown relation write kind — still try resolve, but flag.
            self._diagnostic(
                process_id,
                now,
                {
                    "code": "WRITE_TARGET_KIND_UNEXPECTED",
                    "message": (
                        f"writes_to type={target.type!r} is not table/materialized_view/storage; "
                        "resolving as relation"
                    ),
                    "target_ref": {
                        "type": target.type,
                        "database": target.database,
                        "schema": target.schema,
                        "name": target.name,
                    },
                },
            )
            details["diagnostics"] += 1
        return self._resolve_relation_target(target, process_id, now, details)

    def _resolve_relation_target(
        self,
        target: LoaderTarget,
        process_id: uuid.UUID,
        now: datetime.datetime,
        details: dict,
    ) -> Asset:
        if not target.database or not target.schema or not target.name:
            details["unresolved"] += 1
            details["diagnostics"] += 1
            self._diagnostic(
                process_id,
                now,
                {
                    "code": "TARGET_UNRESOLVED",
                    "message": "relation target requires database, schema, name",
                    "target_ref": {"type": target.type},
                },
            )
            return self._unresolved_target("?", "?", "?", now)
        connection = self._settings.connection_identity
        _qualified, identity_key = relation_identity(
            connection, target.database, target.schema, target.name
        )
        asset = self._store.find_by_identity("postgres", identity_key)
        if asset is not None:
            return asset
        details["unresolved"] += 1
        self._diagnostic(
            process_id,
            now,
            {
                "code": "TARGET_UNRESOLVED",
                "message": f"{target.database}.{target.schema}.{target.name} was not found",
                "target_ref": {
                    "type": target.type,
                    "database": target.database,
                    "schema": target.schema,
                    "name": target.name,
                },
            },
        )
        details["diagnostics"] += 1
        return self._unresolved_target(target.database, target.schema, target.name, now)

    def _unresolved_storage_target(self, kind: str, now: datetime.datetime) -> Asset:
        label = f"unresolved-storage:{kind}"
        qualified_name, identity_key = unresolved_target_identity("_", "_", label)
        return self._store.upsert_asset(
            Asset(
                asset_type=AssetType.STORAGE_LOCATION,
                qualified_name=qualified_name,
                name=label,
                source_provider=PROVIDER,
                identity_key=identity_key,
                first_seen_at=now,
                last_seen_at=now,
                attributes={"unresolved": True, "storage_kind": kind},
            )
        )

    def _upsert_extraction(self, record: ExtractionSourceRecord, now: datetime.datetime) -> Asset:
        qualified_name, identity_key = extraction_source_identity(record.id)
        extract_options = strip_secrets(record.extract_options)
        return self._store.upsert_asset(
            Asset(
                asset_type=AssetType.EXTRACTION_SOURCE,
                qualified_name=qualified_name,
                name=record.name or record.id,
                description=record.descr,
                source_provider=PROVIDER,
                native_id=record.id,
                identity_key=identity_key,
                first_seen_at=now,
                last_seen_at=now,
                attributes={
                    "access_level": record.access_level,
                    "is_active": record.is_active,
                    "extract_source_type_id": record.extract_source_type_id,
                    "extract_options": extract_options,
                    "load_schedule_id": record.load_schedule_id,
                    "tags": record.tags,
                    "comment": record.comment,
                },
            )
        )

    def _upsert_data_source(self, record: ExtractionSourceRecord, now: datetime.datetime) -> Asset:
        native_id = record.data_source_id or record.name or "source"
        qualified_name, identity_key = data_source_identity(native_id)
        return self._store.upsert_asset(
            Asset(
                asset_type=AssetType.DATA_SOURCE,
                qualified_name=qualified_name,
                name=record.data_source_name or native_id,
                source_provider=PROVIDER,
                native_id=native_id,
                identity_key=identity_key,
                first_seen_at=now,
                last_seen_at=now,
            )
        )

    def _upsert_storage(self, record: ExtractionSourceRecord, now: datetime.datetime) -> Asset:
        cleaned = strip_secrets(record.storage_options)
        path = str(cleaned.get("path") or record.id)
        qualified_name, identity_key = storage_location_identity(path)
        return self._store.upsert_asset(
            Asset(
                asset_type=AssetType.STORAGE_LOCATION,
                qualified_name=qualified_name,
                name=path,
                source_provider=PROVIDER,
                identity_key=identity_key,
                first_seen_at=now,
                last_seen_at=now,
                attributes=cleaned,
            )
        )

    def _upsert_process(
        self,
        record: ExtractionSourceRecord,
        handler: dict,
        handler_key: str,
        now: datetime.datetime,
    ) -> Asset:
        qualified_name, identity_key = process_identity(record.id, handler_key)
        return self._store.upsert_asset(
            Asset(
                asset_type=AssetType.PROCESS,
                qualified_name=qualified_name,
                name=str(handler.get("name") or handler.get("module") or handler_key),
                source_provider=PROVIDER,
                identity_key=identity_key,
                first_seen_at=now,
                last_seen_at=now,
                attributes={
                    "handler_type": handler.get("handler_type"),
                    "module": handler.get("module"),
                    "extraction_source_id": record.id,
                },
            )
        )

    def _unresolved_target(self, database: str, schema: str, name: str, now: datetime.datetime) -> Asset:
        qualified_name, identity_key = unresolved_target_identity(database, schema, name)
        return self._store.upsert_asset(
            Asset(
                asset_type=AssetType.TABLE,
                qualified_name=qualified_name,
                name=name,
                source_provider=PROVIDER,
                identity_key=identity_key,
                first_seen_at=now,
                last_seen_at=now,
                attributes={
                    "unresolved": True,
                    "target_ref": {"type": "table", "database": database, "schema": schema, "name": name},
                    "database": database,
                    "schema": schema,
                    "display_name": f"{schema}.{name}",
                },
            )
        )

    def _rel(self, from_id: uuid.UUID, to_id: uuid.UUID, rel_type: RelationshipType) -> None:
        self._store.upsert_relationship(
            Relationship(
                from_asset_id=from_id,
                to_asset_id=to_id,
                relationship_type=rel_type,
                source_provider=PROVIDER,
            )
        )

    def _diagnostic(self, asset_id: uuid.UUID, now: datetime.datetime, payload: dict) -> None:
        self._store.add_diagnostic(
            DiscoveryDiagnostic(
                asset_id=asset_id,
                detected_at=now,
                severity="warning",
                code=str(payload.get("code") or "DIAGNOSTIC"),
                message=str(payload.get("message") or payload.get("code") or "diagnostic"),
                details=payload,
            )
        )
