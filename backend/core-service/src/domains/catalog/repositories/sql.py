from __future__ import annotations

import datetime
import uuid
from collections.abc import Callable
from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import Session

from domains.catalog.models import (
    Asset,
    AssetColumn,
    AssetQuery,
    AssetSnapshot,
    AssetStatus,
    AssetType,
    ChangeEvent,
    ChangeQuery,
    ChangeType,
    CollectionRun,
    CollectorStatus,
    DiscoveryDiagnostic,
    Relationship,
    RelationshipType,
)
from infrastructure.db.models.portal import (
    PortalAssetColumnDbModel,
    PortalAssetDbModel,
    PortalAssetSnapshotDbModel,
    PortalChangeEventDbModel,
    PortalCollectionRunDbModel,
    PortalDiscoveryDiagnosticDbModel,
    PortalRelationshipDbModel,
)
from infrastructure.db.session_management import SessionProvider


class SqlPortalStore:
    """Portal snapshot store backed by app DB schema `sol_dwh_portal` (portal_* tables)."""

    def __init__(self, session_factory: Callable[[], Session] | None = None) -> None:
        self._session_factory = session_factory or SessionProvider.create_session

    @contextmanager
    def _session(self, *, commit: bool = False) -> Iterator[Session]:
        session = self._session_factory()
        try:
            yield session
            if commit:
                session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def upsert_asset(self, asset: Asset) -> Asset:
        with self._session(commit=True) as session:
            existing = session.scalar(
                select(PortalAssetDbModel).where(
                    PortalAssetDbModel.source_provider == asset.source_provider,
                    PortalAssetDbModel.identity_key == asset.identity_key,
                )
            )
            if existing is not None:
                asset.id = existing.id
                asset.first_seen_at = existing.first_seen_at
                existing.asset_type = asset.asset_type.value
                existing.qualified_name = asset.qualified_name
                existing.name = asset.name
                existing.description = asset.description
                existing.native_id = asset.native_id
                existing.last_seen_at = asset.last_seen_at
                existing.deleted_at = asset.deleted_at
                existing.attributes = dict(asset.attributes or {})
                session.flush()
                return self._asset_from_row(existing)
            row = PortalAssetDbModel(
                id=asset.id,
                asset_type=asset.asset_type.value,
                qualified_name=asset.qualified_name,
                name=asset.name,
                description=asset.description,
                source_provider=asset.source_provider,
                native_id=asset.native_id,
                identity_key=asset.identity_key,
                first_seen_at=asset.first_seen_at,
                last_seen_at=asset.last_seen_at,
                deleted_at=asset.deleted_at,
                attributes=dict(asset.attributes or {}),
            )
            session.add(row)
            session.flush()
            return self._asset_from_row(row)

    def get_asset(self, asset_id: uuid.UUID, *, include_deleted: bool = True) -> Asset | None:
        with self._session() as session:
            row = session.get(PortalAssetDbModel, asset_id)
            if row is None:
                return None
            if not include_deleted and row.deleted_at is not None:
                return None
            return self._asset_from_row(row)

    def find_by_identity(self, source_provider: str, identity_key: str) -> Asset | None:
        with self._session() as session:
            row = session.scalar(
                select(PortalAssetDbModel).where(
                    PortalAssetDbModel.source_provider == source_provider,
                    PortalAssetDbModel.identity_key == identity_key,
                )
            )
            return self._asset_from_row(row) if row else None

    def find_by_qualified_name(
        self, qualified_name: str, *, include_deleted: bool = False
    ) -> Asset | None:
        with self._session() as session:
            stmt = select(PortalAssetDbModel).where(PortalAssetDbModel.qualified_name == qualified_name)
            if not include_deleted:
                stmt = stmt.where(PortalAssetDbModel.deleted_at.is_(None))
            row = session.scalar(stmt)
            return self._asset_from_row(row) if row else None

    def list_assets(self, query: AssetQuery) -> tuple[list[Asset], int]:
        with self._session() as session:
            stmt = select(PortalAssetDbModel)
            if query.status == AssetStatus.ACTIVE:
                stmt = stmt.where(PortalAssetDbModel.deleted_at.is_(None))
            elif query.status == AssetStatus.DELETED:
                stmt = stmt.where(PortalAssetDbModel.deleted_at.is_not(None))
            if query.asset_type is not None:
                stmt = stmt.where(PortalAssetDbModel.asset_type == query.asset_type.value)
            if query.source:
                stmt = stmt.where(PortalAssetDbModel.source_provider == query.source)
            if query.q:
                needle = f"%{query.q.lower()}%"
                stmt = stmt.where(
                    or_(
                        func.lower(PortalAssetDbModel.qualified_name).like(needle),
                        func.lower(PortalAssetDbModel.name).like(needle),
                        func.lower(func.coalesce(PortalAssetDbModel.description, "")).like(needle),
                    )
                )
            if query.changed_since is not None:
                changed_ids = select(PortalChangeEventDbModel.asset_id).where(
                    PortalChangeEventDbModel.detected_at >= query.changed_since
                )
                stmt = stmt.where(PortalAssetDbModel.id.in_(changed_ids))

            rows = list(session.scalars(stmt).all())
            items = [self._asset_from_row(row) for row in rows]
            if query.database:
                items = [
                    item
                    for item in items
                    if item.attributes.get("database") == query.database
                    or item.qualified_name.startswith(f"{query.database}.")
                    or item.name == query.database
                ]
            if query.schema_name:
                items = [
                    item
                    for item in items
                    if item.attributes.get("schema") == query.schema_name
                    or f".{query.schema_name}." in f".{item.qualified_name}."
                ]
            reverse = query.sort.startswith("-")
            sort_key = query.sort.lstrip("-")
            items.sort(key=lambda item: getattr(item, sort_key, item.qualified_name), reverse=reverse)
            total = len(items)
            start = max(query.page - 1, 0) * query.page_size
            return items[start : start + query.page_size], total

    def replace_columns(self, asset_id: uuid.UUID, columns: list[AssetColumn]) -> None:
        with self._session(commit=True) as session:
            session.execute(
                delete(PortalAssetColumnDbModel).where(PortalAssetColumnDbModel.asset_id == asset_id)
            )
            for column in columns:
                session.add(
                    PortalAssetColumnDbModel(
                        asset_id=asset_id,
                        ordinal=column.ordinal,
                        name=column.name,
                        data_type=column.data_type,
                        nullable=column.nullable,
                        description=column.description,
                    )
                )

    def get_columns(self, asset_id: uuid.UUID) -> list[AssetColumn]:
        with self._session() as session:
            rows = session.scalars(
                select(PortalAssetColumnDbModel)
                .where(PortalAssetColumnDbModel.asset_id == asset_id)
                .order_by(PortalAssetColumnDbModel.ordinal)
            ).all()
            return [self._column_from_row(row) for row in rows]

    def add_snapshot(self, snapshot: AssetSnapshot) -> AssetSnapshot:
        with self._session(commit=True) as session:
            row = PortalAssetSnapshotDbModel(
                id=snapshot.id,
                asset_id=snapshot.asset_id,
                snapshot_at=snapshot.snapshot_at,
                table_bytes=snapshot.table_bytes,
                index_bytes=snapshot.index_bytes,
                total_bytes=snapshot.total_bytes,
                row_estimate=snapshot.row_estimate,
                object_count=snapshot.object_count,
                structure_hash=snapshot.structure_hash,
            )
            session.add(row)
            session.flush()
            return self._snapshot_from_row(row)

    def latest_snapshot(self, asset_id: uuid.UUID) -> AssetSnapshot | None:
        with self._session() as session:
            row = session.scalar(
                select(PortalAssetSnapshotDbModel)
                .where(PortalAssetSnapshotDbModel.asset_id == asset_id)
                .order_by(PortalAssetSnapshotDbModel.snapshot_at.desc())
                .limit(1)
            )
            return self._snapshot_from_row(row) if row else None

    def list_snapshots(
        self,
        *,
        asset_id: uuid.UUID | None = None,
        since: datetime.datetime | None = None,
        until: datetime.datetime | None = None,
    ) -> list[AssetSnapshot]:
        with self._session() as session:
            stmt = select(PortalAssetSnapshotDbModel)
            if asset_id is not None:
                stmt = stmt.where(PortalAssetSnapshotDbModel.asset_id == asset_id)
            if since is not None:
                stmt = stmt.where(PortalAssetSnapshotDbModel.snapshot_at >= since)
            if until is not None:
                stmt = stmt.where(PortalAssetSnapshotDbModel.snapshot_at <= until)
            stmt = stmt.order_by(PortalAssetSnapshotDbModel.snapshot_at)
            return [self._snapshot_from_row(row) for row in session.scalars(stmt).all()]

    def upsert_relationship(self, relationship: Relationship) -> Relationship:
        with self._session(commit=True) as session:
            existing = session.scalar(
                select(PortalRelationshipDbModel).where(
                    PortalRelationshipDbModel.from_asset_id == relationship.from_asset_id,
                    PortalRelationshipDbModel.to_asset_id == relationship.to_asset_id,
                    PortalRelationshipDbModel.relationship_type
                    == relationship.relationship_type.value,
                )
            )
            if existing is not None:
                relationship.id = existing.id
                existing.source_provider = relationship.source_provider
                existing.native_id = relationship.native_id
                existing.attributes = dict(relationship.attributes or {})
                session.flush()
                return self._relationship_from_row(existing)
            row = PortalRelationshipDbModel(
                id=relationship.id,
                from_asset_id=relationship.from_asset_id,
                to_asset_id=relationship.to_asset_id,
                relationship_type=relationship.relationship_type.value,
                source_provider=relationship.source_provider,
                native_id=relationship.native_id,
                attributes=dict(relationship.attributes or {}),
            )
            session.add(row)
            session.flush()
            return self._relationship_from_row(row)

    def list_relationships(
        self,
        *,
        asset_id: uuid.UUID | None = None,
        types: set[RelationshipType] | None = None,
    ) -> list[Relationship]:
        with self._session() as session:
            stmt = select(PortalRelationshipDbModel)
            if asset_id is not None:
                stmt = stmt.where(
                    or_(
                        PortalRelationshipDbModel.from_asset_id == asset_id,
                        PortalRelationshipDbModel.to_asset_id == asset_id,
                    )
                )
            if types is not None:
                stmt = stmt.where(
                    PortalRelationshipDbModel.relationship_type.in_([item.value for item in types])
                )
            return [self._relationship_from_row(row) for row in session.scalars(stmt).all()]

    def add_change(self, event: ChangeEvent) -> ChangeEvent:
        with self._session(commit=True) as session:
            row = PortalChangeEventDbModel(
                id=event.id,
                asset_id=event.asset_id,
                detected_at=event.detected_at,
                change_type=event.change_type.value,
                details=dict(event.details or {}),
            )
            session.add(row)
            session.flush()
            return self._change_from_row(row)

    def get_change(self, change_id: uuid.UUID) -> ChangeEvent | None:
        with self._session() as session:
            row = session.get(PortalChangeEventDbModel, change_id)
            return self._change_from_row(row) if row else None

    def list_changes(self, query: ChangeQuery) -> tuple[list[ChangeEvent], int]:
        with self._session() as session:
            stmt = select(PortalChangeEventDbModel)
            if query.change_type is not None:
                stmt = stmt.where(PortalChangeEventDbModel.change_type == query.change_type.value)
            if query.since is not None:
                stmt = stmt.where(PortalChangeEventDbModel.detected_at >= query.since)
            if query.until is not None:
                stmt = stmt.where(PortalChangeEventDbModel.detected_at <= query.until)
            if query.asset_id is not None:
                stmt = stmt.where(PortalChangeEventDbModel.asset_id == query.asset_id)
            stmt = stmt.order_by(PortalChangeEventDbModel.detected_at.desc())
            rows = list(session.scalars(stmt).all())
            total = len(rows)
            start = max(query.page - 1, 0) * query.page_size
            page = rows[start : start + query.page_size]
            return [self._change_from_row(row) for row in page], total

    def add_diagnostic(self, diagnostic: DiscoveryDiagnostic) -> DiscoveryDiagnostic:
        with self._session(commit=True) as session:
            row = PortalDiscoveryDiagnosticDbModel(
                id=diagnostic.id,
                asset_id=diagnostic.asset_id,
                detected_at=diagnostic.detected_at,
                severity=diagnostic.severity,
                code=diagnostic.code,
                message=diagnostic.message,
                details=dict(diagnostic.details or {}),
            )
            session.add(row)
            session.flush()
            return self._diagnostic_from_row(row)

    def list_diagnostics(self, asset_id: uuid.UUID | None = None) -> list[DiscoveryDiagnostic]:
        with self._session() as session:
            stmt = select(PortalDiscoveryDiagnosticDbModel)
            if asset_id is not None:
                stmt = stmt.where(PortalDiscoveryDiagnosticDbModel.asset_id == asset_id)
            return [self._diagnostic_from_row(row) for row in session.scalars(stmt).all()]

    def add_collection_run(self, run: CollectionRun) -> CollectionRun:
        with self._session(commit=True) as session:
            row = PortalCollectionRunDbModel(
                id=run.id,
                collector_name=run.collector_name,
                started_at=run.started_at,
                finished_at=run.finished_at,
                status=run.status.value,
                message=run.message,
                details=dict(run.details or {}),
            )
            session.add(row)
            session.flush()
            return self._run_from_row(row)

    def latest_runs(self) -> list[CollectionRun]:
        with self._session() as session:
            rows = session.scalars(
                select(PortalCollectionRunDbModel).order_by(PortalCollectionRunDbModel.started_at)
            ).all()
            latest: dict[str, CollectionRun] = {}
            for row in rows:
                latest[row.collector_name] = self._run_from_row(row)
            return list(latest.values())

    def mark_missing_as_deleted(
        self,
        source_provider: str,
        seen_ids: set[uuid.UUID],
        deleted_at: datetime.datetime,
        asset_types: set[str] | None = None,
    ) -> list[Asset]:
        with self._session(commit=True) as session:
            stmt = select(PortalAssetDbModel).where(
                PortalAssetDbModel.source_provider == source_provider,
                PortalAssetDbModel.deleted_at.is_(None),
            )
            if asset_types:
                stmt = stmt.where(PortalAssetDbModel.asset_type.in_(list(asset_types)))
            removed: list[Asset] = []
            for row in session.scalars(stmt).all():
                if row.id in seen_ids:
                    continue
                row.deleted_at = deleted_at
                removed.append(self._asset_from_row(row))
            return removed

    def is_empty(self) -> bool:
        with self._session() as session:
            return session.scalar(select(func.count()).select_from(PortalAssetDbModel)) == 0

    @staticmethod
    def _asset_from_row(row: PortalAssetDbModel) -> Asset:
        return Asset(
            id=row.id,
            asset_type=AssetType(row.asset_type),
            qualified_name=row.qualified_name,
            name=row.name,
            description=row.description,
            source_provider=row.source_provider,
            native_id=row.native_id,
            identity_key=row.identity_key,
            first_seen_at=row.first_seen_at,
            last_seen_at=row.last_seen_at,
            deleted_at=row.deleted_at,
            attributes=dict(row.attributes or {}),
        )

    @staticmethod
    def _column_from_row(row: PortalAssetColumnDbModel) -> AssetColumn:
        return AssetColumn(
            asset_id=row.asset_id,
            ordinal=row.ordinal,
            name=row.name,
            data_type=row.data_type,
            nullable=row.nullable,
            description=row.description,
        )

    @staticmethod
    def _snapshot_from_row(row: PortalAssetSnapshotDbModel) -> AssetSnapshot:
        return AssetSnapshot(
            id=row.id,
            asset_id=row.asset_id,
            snapshot_at=row.snapshot_at,
            table_bytes=row.table_bytes,
            index_bytes=row.index_bytes,
            total_bytes=row.total_bytes,
            row_estimate=row.row_estimate,
            object_count=row.object_count,
            structure_hash=row.structure_hash,
        )

    @staticmethod
    def _relationship_from_row(row: PortalRelationshipDbModel) -> Relationship:
        return Relationship(
            id=row.id,
            from_asset_id=row.from_asset_id,
            to_asset_id=row.to_asset_id,
            relationship_type=RelationshipType(row.relationship_type),
            source_provider=row.source_provider,
            native_id=row.native_id,
            attributes=dict(row.attributes or {}),
        )

    @staticmethod
    def _change_from_row(row: PortalChangeEventDbModel) -> ChangeEvent:
        return ChangeEvent(
            id=row.id,
            asset_id=row.asset_id,
            detected_at=row.detected_at,
            change_type=ChangeType(row.change_type),
            details=dict(row.details or {}),
        )

    @staticmethod
    def _diagnostic_from_row(row: PortalDiscoveryDiagnosticDbModel) -> DiscoveryDiagnostic:
        return DiscoveryDiagnostic(
            id=row.id,
            asset_id=row.asset_id,
            detected_at=row.detected_at,
            severity=row.severity,
            code=row.code,
            message=row.message,
            details=dict(row.details or {}),
        )

    @staticmethod
    def _run_from_row(row: PortalCollectionRunDbModel) -> CollectionRun:
        return CollectionRun(
            id=row.id,
            collector_name=row.collector_name,
            started_at=row.started_at,
            finished_at=row.finished_at,
            status=CollectorStatus(row.status),
            message=row.message,
            details=dict(row.details or {}),
        )
