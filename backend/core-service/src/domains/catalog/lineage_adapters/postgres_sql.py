from __future__ import annotations

import datetime
from typing import Any

from domains.catalog.identity import relation_identity, unresolved_target_identity
from domains.catalog.lineage_adapters.runs import record_adapter_run, skipped_run
from domains.catalog.models import (
    Asset,
    AssetType,
    CollectionRun,
    CollectorStatus,
    DiscoveryDiagnostic,
    Relationship,
    RelationshipType,
)
from domains.catalog.providers.metadata import RelationDependency
from domains.catalog.repositories.ports import PortalStore
from settings.portal import DwhCollectorSettings

PROVIDER = "postgres"


class PostgresSqlLineageAdapter:
    """Restore VIEW/MATERIALIZED_VIEW DERIVED_FROM edges from PostgreSQL catalog."""

    name = "postgres_sql"

    def __init__(
        self,
        store: PortalStore,
        settings: DwhCollectorSettings | None = None,
        *,
        metadata_provider: Any | None = None,
        **_kwargs: Any,
    ):
        self._store = store
        self._settings = settings or DwhCollectorSettings()
        self._provider = metadata_provider

    def collect(self, now: datetime.datetime | None = None) -> CollectionRun:
        started = now or datetime.datetime.now(datetime.timezone.utc)
        provider = self._provider
        if provider is None or not hasattr(provider, "list_relation_dependencies"):
            return skipped_run(
                self._store,
                name=self.name,
                started=started,
                reason="PROVIDER_UNAVAILABLE",
                message="SQL lineage provider does not expose relation dependencies",
            )
        details = {"edges": 0, "unresolved": 0, "diagnostics": 0}
        try:
            dependencies: list[RelationDependency] = provider.list_relation_dependencies()
            for item in dependencies:
                self._ingest(item, started, details)
            message = f"Recorded {details['edges']} SQL derived-from edges"
            status = (
                CollectorStatus.PARTIAL
                if details["diagnostics"] and details["edges"]
                else CollectorStatus.SUCCESS
            )
        except Exception as exc:
            return record_adapter_run(
                self._store,
                name=self.name,
                started=started,
                status=CollectorStatus.FAILED,
                message=str(exc),
                details={"error": str(exc)},
            )
        return record_adapter_run(
            self._store,
            name=self.name,
            started=started,
            status=status,
            message=message,
            details=details,
        )

    def _ingest(
        self, item: RelationDependency, now: datetime.datetime, details: dict
    ) -> None:
        connection = self._settings.connection_identity
        database = item.database
        _qn, view_key = relation_identity(
            connection, database, item.dependent_schema, item.dependent_name
        )
        _qn, source_key = relation_identity(
            connection, database, item.source_schema, item.source_name
        )
        view = self._store.find_by_identity(PROVIDER, view_key)
        if view is None:
            details["diagnostics"] += 1
            self._diagnostic(
                None,
                now,
                {
                    "code": "VIEW_NOT_IN_CATALOG",
                    "message": (
                        f"{database}.{item.dependent_schema}.{item.dependent_name} "
                        "was not in the catalog snapshot"
                    ),
                },
            )
            return
        source = self._store.find_by_identity(PROVIDER, source_key)
        if source is None:
            source = self._unresolved(
                database, item.source_schema, item.source_name, now
            )
            details["unresolved"] += 1
            details["diagnostics"] += 1
            self._diagnostic(
                view.id,
                now,
                {
                    "code": "SOURCE_UNRESOLVED",
                    "message": (
                        f"{database}.{item.source_schema}.{item.source_name} "
                        "was not found"
                    ),
                    "target_ref": {
                        "database": database,
                        "schema": item.source_schema,
                        "name": item.source_name,
                    },
                },
            )
        self._store.upsert_relationship(
            Relationship(
                from_asset_id=view.id,
                to_asset_id=source.id,
                relationship_type=RelationshipType.DERIVED_FROM,
                source_provider=PROVIDER,
            )
        )
        details["edges"] += 1

    def _unresolved(
        self, database: str, schema: str, name: str, now: datetime.datetime
    ) -> Asset:
        qualified_name, identity_key = unresolved_target_identity(database, schema, name)
        existing = self._store.find_by_identity(PROVIDER, identity_key)
        if existing is not None:
            existing.last_seen_at = now
            return self._store.upsert_asset(existing)
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
                    "target_ref": {"database": database, "schema": schema, "name": name},
                    "database": database,
                    "schema": schema,
                    "display_name": f"{schema}.{name}",
                },
            )
        )

    def _diagnostic(
        self, asset_id, now: datetime.datetime, payload: dict
    ) -> None:
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
