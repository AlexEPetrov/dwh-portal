from __future__ import annotations

import datetime
import uuid
from typing import Protocol

from domains.catalog.models import (
    Asset,
    AssetColumn,
    AssetQuery,
    AssetSnapshot,
    ChangeEvent,
    ChangeQuery,
    CollectionRun,
    DiscoveryDiagnostic,
    Relationship,
    RelationshipType,
)


class PortalStore(Protocol):
    """Snapshot persistence used by Portal API and collectors."""

    def upsert_asset(self, asset: Asset) -> Asset: ...

    def get_asset(self, asset_id: uuid.UUID, *, include_deleted: bool = True) -> Asset | None: ...

    def find_by_identity(self, source_provider: str, identity_key: str) -> Asset | None: ...

    def find_by_qualified_name(
        self, qualified_name: str, *, include_deleted: bool = False
    ) -> Asset | None: ...

    def list_assets(self, query: AssetQuery) -> tuple[list[Asset], int]: ...

    def replace_columns(self, asset_id: uuid.UUID, columns: list[AssetColumn]) -> None: ...

    def get_columns(self, asset_id: uuid.UUID) -> list[AssetColumn]: ...

    def add_snapshot(self, snapshot: AssetSnapshot) -> AssetSnapshot: ...

    def latest_snapshot(self, asset_id: uuid.UUID) -> AssetSnapshot | None: ...

    def list_snapshots(
        self,
        *,
        asset_id: uuid.UUID | None = None,
        since: datetime.datetime | None = None,
        until: datetime.datetime | None = None,
    ) -> list[AssetSnapshot]: ...

    def upsert_relationship(self, relationship: Relationship) -> Relationship: ...

    def list_relationships(
        self,
        *,
        asset_id: uuid.UUID | None = None,
        types: set[RelationshipType] | None = None,
    ) -> list[Relationship]: ...

    def add_change(self, event: ChangeEvent) -> ChangeEvent: ...

    def get_change(self, change_id: uuid.UUID) -> ChangeEvent | None: ...

    def list_changes(self, query: ChangeQuery) -> tuple[list[ChangeEvent], int]: ...

    def add_diagnostic(self, diagnostic: DiscoveryDiagnostic) -> DiscoveryDiagnostic: ...

    def list_diagnostics(self, asset_id: uuid.UUID | None = None) -> list[DiscoveryDiagnostic]: ...

    def add_collection_run(self, run: CollectionRun) -> CollectionRun: ...

    def latest_runs(self) -> list[CollectionRun]: ...

    def mark_missing_as_deleted(
        self,
        source_provider: str,
        seen_ids: set[uuid.UUID],
        deleted_at: datetime.datetime,
        asset_types: set[str] | None = None,
    ) -> list[Asset]: ...

    def is_empty(self) -> bool: ...

    def purge(self) -> None: ...
