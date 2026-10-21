from __future__ import annotations

import datetime
import uuid
from collections.abc import Callable
from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import and_, case, delete, func, or_, select, text
from sqlalchemy.orm import Session

from domains.catalog.models import (
    Asset,
    AssetColumn,
    AssetCountSummary,
    AssetListEntry,
    AssetQuery,
    AssetSnapshot,
    AssetStatus,
    AssetType,
    ChangeCountSummary,
    ChangeEvent,
    ChangeQuery,
    ChangeType,
    CollectionRun,
    CollectorStatus,
    DiscoveryDiagnostic,
    Relationship,
    RelationshipType,
    SchemaStorageRow,
    StorageObjectRow,
    StorageSummary,
)
from infrastructure.db.models.portal import (
    PORTAL_SCHEMA,
    PortalAssetColumnDbModel,
    PortalAssetDbModel,
    PortalAssetSnapshotDbModel,
    PortalChangeEventDbModel,
    PortalCollectionRunDbModel,
    PortalDiscoveryDiagnosticDbModel,
    PortalRelationshipDbModel,
)
from infrastructure.db.session_management import SessionProvider

_ASSET_SORT_COLUMNS = {
    "id": PortalAssetDbModel.id,
    "asset_type": PortalAssetDbModel.asset_type,
    "qualified_name": PortalAssetDbModel.qualified_name,
    "name": PortalAssetDbModel.name,
    "description": PortalAssetDbModel.description,
    "source_provider": PortalAssetDbModel.source_provider,
    "native_id": PortalAssetDbModel.native_id,
    "identity_key": PortalAssetDbModel.identity_key,
    "first_seen_at": PortalAssetDbModel.first_seen_at,
    "last_seen_at": PortalAssetDbModel.last_seen_at,
    "deleted_at": PortalAssetDbModel.deleted_at,
}

_STORAGE_TYPE_VALUES = (
    AssetType.TABLE.value,
    AssetType.VIEW.value,
    AssetType.MATERIALIZED_VIEW.value,
    AssetType.STORAGE_LOCATION.value,
)


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
            filtered = self._filtered_assets(query)
            total = session.scalar(select(func.count()).select_from(filtered.subquery())) or 0
            stmt = self._paged(filtered, query)
            rows = session.scalars(stmt).all()
            return [self._asset_from_row(row) for row in rows], int(total)

    def list_asset_page(self, query: AssetQuery) -> tuple[list[AssetListEntry], int]:
        """Load one grid page, its latest snapshot, and its latest change time.

        The page is a single SELECT. The total is a separate COUNT of the same
        filter so an empty page still reports how many rows matched.
        """
        with self._session() as session:
            filtered = self._filtered_assets(query)
            total = session.scalar(select(func.count()).select_from(filtered.subquery())) or 0
            stmt = self._asset_page_stmt(query)
            entries = [
                AssetListEntry(
                    asset=self._asset_from_row(asset_row),
                    snapshot=(
                        self._snapshot_from_row(snapshot_row) if snapshot_row is not None else None
                    ),
                    last_changed_at=changed_at,
                )
                for asset_row, snapshot_row, changed_at in session.execute(stmt).all()
            ]
            return entries, int(total)

    def count_assets(self) -> AssetCountSummary:
        """Count every active asset. Not bounded by list page size."""
        with self._session() as session:
            rows = session.execute(
                select(PortalAssetDbModel.asset_type, func.count())
                .where(PortalAssetDbModel.deleted_at.is_(None))
                .group_by(PortalAssetDbModel.asset_type)
            ).all()
        by_type = {asset_type: int(count) for asset_type, count in rows}
        tables = by_type.get(AssetType.TABLE.value, 0)
        views = by_type.get(AssetType.VIEW.value, 0) + by_type.get(
            AssetType.MATERIALIZED_VIEW.value, 0
        )
        return AssetCountSummary(total=sum(by_type.values()), tables=tables, views=views)

    def summarize_storage(self, *, largest_limit: int = 20) -> StorageSummary:
        """Aggregate the latest snapshot of each sized active object."""
        with self._session() as session:
            latest_times = (
                select(
                    PortalAssetSnapshotDbModel.asset_id.label("asset_id"),
                    func.max(PortalAssetSnapshotDbModel.snapshot_at).label("snapshot_at"),
                )
                .group_by(PortalAssetSnapshotDbModel.asset_id)
                .subquery()
            )
            latest = (
                select(PortalAssetSnapshotDbModel)
                .join(
                    latest_times,
                    and_(
                        PortalAssetSnapshotDbModel.asset_id == latest_times.c.asset_id,
                        PortalAssetSnapshotDbModel.snapshot_at == latest_times.c.snapshot_at,
                    ),
                )
                .subquery()
            )
            item_total = func.coalesce(
                latest.c.total_bytes,
                func.coalesce(latest.c.table_bytes, 0) + func.coalesce(latest.c.index_bytes, 0),
            )
            schema_name = func.coalesce(
                PortalAssetDbModel.attributes["schema"].astext,
                PortalAssetDbModel.asset_type,
            )
            sized = (
                PortalAssetDbModel.deleted_at.is_(None),
                PortalAssetDbModel.asset_type.in_(_STORAGE_TYPE_VALUES),
            )
            totals = session.execute(
                select(
                    func.max(latest.c.snapshot_at),
                    func.coalesce(func.sum(latest.c.table_bytes), 0),
                    func.coalesce(func.sum(latest.c.index_bytes), 0),
                    func.coalesce(func.sum(item_total), 0),
                )
                .select_from(PortalAssetDbModel)
                .join(latest, latest.c.asset_id == PortalAssetDbModel.id)
                .where(*sized)
            ).one()
            schema_rows = [
                SchemaStorageRow(schema_name=str(name), total_bytes=int(size or 0))
                for name, size in session.execute(
                    select(schema_name, func.sum(item_total))
                    .select_from(PortalAssetDbModel)
                    .join(latest, latest.c.asset_id == PortalAssetDbModel.id)
                    .where(*sized)
                    .group_by(schema_name)
                    .order_by(func.sum(item_total).desc())
                ).all()
            ]
            largest_rows = session.execute(
                select(
                    PortalAssetDbModel,
                    latest.c.table_bytes,
                    latest.c.index_bytes,
                    latest.c.total_bytes,
                    latest.c.row_estimate,
                )
                .join(latest, latest.c.asset_id == PortalAssetDbModel.id)
                .where(*sized)
                .order_by(item_total.desc(), PortalAssetDbModel.qualified_name.asc())
                .limit(largest_limit)
            ).all()
            largest = []
            for asset_row, table_b, index_b, total_b, row_estimate in largest_rows:
                item_total_bytes = int(
                    total_b if total_b is not None else (table_b or 0) + (index_b or 0)
                )
                largest.append(
                    StorageObjectRow(
                        asset_id=asset_row.id,
                        qualified_name=asset_row.qualified_name,
                        display_name=str(
                            (asset_row.attributes or {}).get("display_name")
                            or asset_row.qualified_name
                        ),
                        asset_type=AssetType(asset_row.asset_type),
                        total_bytes=item_total_bytes,
                        table_bytes=table_b,
                        index_bytes=index_b,
                        row_estimate=row_estimate,
                    )
                )
            return StorageSummary(
                as_of=totals[0],
                table_bytes=int(totals[1] or 0),
                index_bytes=int(totals[2] or 0),
                total_bytes=int(totals[3] or 0),
                by_schema=schema_rows,
                largest_objects=largest,
            )

    def count_changes(
        self,
        *,
        since: datetime.datetime | None = None,
        until: datetime.datetime | None = None,
    ) -> ChangeCountSummary:
        with self._session() as session:
            stmt = select(PortalChangeEventDbModel.change_type, func.count())
            if since is not None:
                stmt = stmt.where(PortalChangeEventDbModel.detected_at >= since)
            if until is not None:
                stmt = stmt.where(PortalChangeEventDbModel.detected_at <= until)
            rows = session.execute(stmt.group_by(PortalChangeEventDbModel.change_type)).all()
        by_type = {change_type: int(count) for change_type, count in rows}
        added = by_type.get(ChangeType.ADDED.value, 0)
        removed = by_type.get(ChangeType.REMOVED.value, 0)
        total = sum(by_type.values())
        return ChangeCountSummary(
            total=total,
            added=added,
            changed=total - added - removed,
            removed=removed,
        )

    def schema_descriptions(self) -> dict[str, str]:
        with self._session() as session:
            rows = session.scalars(
                select(PortalAssetDbModel).where(
                    PortalAssetDbModel.deleted_at.is_(None),
                    PortalAssetDbModel.asset_type == AssetType.SCHEMA.value,
                )
            ).all()
        descriptions: dict[str, str] = {}
        for row in rows:
            if not row.description:
                continue
            name = (row.attributes or {}).get("schema") or row.name
            if isinstance(name, str):
                descriptions[name] = row.description
        return descriptions

    def _asset_page_stmt(self, query: AssetQuery):
        latest_change_at = (
            select(PortalChangeEventDbModel.detected_at)
            .where(PortalChangeEventDbModel.asset_id == PortalAssetDbModel.id)
            .order_by(PortalChangeEventDbModel.detected_at.desc())
            .limit(1)
            .correlate(PortalAssetDbModel)
            .scalar_subquery()
        )
        latest_snapshot_id = (
            select(PortalAssetSnapshotDbModel.id)
            .where(PortalAssetSnapshotDbModel.asset_id == PortalAssetDbModel.id)
            .order_by(PortalAssetSnapshotDbModel.snapshot_at.desc())
            .limit(1)
            .correlate(PortalAssetDbModel)
            .scalar_subquery()
        )
        stmt = select(
            PortalAssetDbModel,
            PortalAssetSnapshotDbModel,
            latest_change_at.label("last_changed_at"),
        ).outerjoin(
            PortalAssetSnapshotDbModel,
            PortalAssetSnapshotDbModel.id == latest_snapshot_id,
        )
        clauses = self._asset_clauses(query)
        if clauses:
            stmt = stmt.where(*clauses)
        return self._paged(stmt, query)

    def _filtered_assets(self, query: AssetQuery):
        stmt = select(PortalAssetDbModel)
        clauses = self._asset_clauses(query)
        if clauses:
            stmt = stmt.where(*clauses)
        return stmt

    @staticmethod
    def _asset_clauses(query: AssetQuery) -> list:
        model = PortalAssetDbModel
        clauses = []
        if query.status == AssetStatus.ACTIVE:
            clauses.append(model.deleted_at.is_(None))
        elif query.status == AssetStatus.DELETED:
            clauses.append(model.deleted_at.is_not(None))
        if query.asset_types:
            clauses.append(model.asset_type.in_([item.value for item in query.asset_types]))
        elif query.asset_type is not None:
            clauses.append(model.asset_type == query.asset_type.value)
        if query.source:
            clauses.append(model.source_provider == query.source)
        if query.q:
            needle = f"%{query.q.lower()}%"
            clauses.append(
                or_(
                    func.lower(model.qualified_name).like(needle),
                    func.lower(model.name).like(needle),
                    func.lower(func.coalesce(model.description, "")).like(needle),
                )
            )
        if query.changed_since is not None:
            changed_ids = select(PortalChangeEventDbModel.asset_id).where(
                PortalChangeEventDbModel.detected_at >= query.changed_since
            )
            clauses.append(model.id.in_(changed_ids))
        if query.database:
            clauses.append(
                or_(
                    model.attributes["database"].astext == query.database,
                    model.qualified_name.startswith(f"{query.database}.", autoescape=True),
                    model.name == query.database,
                )
            )
        if query.schema_name:
            dotted = func.concat(".", model.qualified_name, ".")
            clauses.append(
                or_(
                    model.attributes["schema"].astext == query.schema_name,
                    dotted.contains(f".{query.schema_name}.", autoescape=True),
                )
            )
        return clauses

    @staticmethod
    def _asset_order(query: AssetQuery) -> list:
        reverse = query.sort.startswith("-")
        key = query.sort.lstrip("-")
        if key == "status":
            column = case((PortalAssetDbModel.deleted_at.is_(None), 0), else_=1)
        else:
            column = _ASSET_SORT_COLUMNS.get(key, PortalAssetDbModel.qualified_name)
        primary = column.desc() if reverse else column.asc()
        tie = PortalAssetDbModel.id.desc() if reverse else PortalAssetDbModel.id.asc()
        return [primary, tie]

    @staticmethod
    def _paged(stmt, query: AssetQuery):
        offset = max(query.page - 1, 0) * query.page_size
        return (
            stmt.order_by(*SqlPortalStore._asset_order(query))
            .offset(offset)
            .limit(query.page_size)
        )

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

    def purge(self) -> None:
        """Delete all portal snapshot rows. Does not touch DWH or other app schemas."""
        tables = (
            "portal_asset_columns",
            "portal_asset_snapshots",
            "portal_relationships",
            "portal_change_events",
            "portal_discovery_diagnostics",
            "portal_collection_runs",
            "portal_assets",
        )
        qualified = ", ".join(f'"{PORTAL_SCHEMA}".{name}' for name in tables)
        with self._session(commit=True) as session:
            session.execute(text(f"TRUNCATE TABLE {qualified} RESTART IDENTITY CASCADE"))

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
