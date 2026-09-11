from __future__ import annotations

import datetime
import uuid
from typing import Any, Optional

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import text

from infrastructure.db.models.base import Base

PORTAL_SCHEMA = "portal"
PORTAL_TABLE_ARGS = {"schema": PORTAL_SCHEMA}


class PortalAssetDbModel(Base):
    __tablename__ = "assets"
    __table_args__ = (
        UniqueConstraint("source_provider", "identity_key", name="uq_portal_asset_identity"),
        Index("ix_portal_assets_type", "asset_type"),
        Index("ix_portal_assets_qualified_name", "qualified_name"),
        Index("ix_portal_assets_deleted_at", "deleted_at"),
        PORTAL_TABLE_ARGS,
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    asset_type: Mapped[str] = mapped_column(String(64))
    qualified_name: Mapped[str] = mapped_column(String(512))
    name: Mapped[str] = mapped_column(String(256))
    description: Mapped[Optional[str]] = mapped_column(Text())
    source_provider: Mapped[str] = mapped_column(String(64))
    native_id: Mapped[Optional[str]] = mapped_column(String(256))
    identity_key: Mapped[str] = mapped_column(String(512))
    first_seen_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(timezone=True))
    attributes: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)


class PortalAssetColumnDbModel(Base):
    __tablename__ = "asset_columns"
    __table_args__ = (
        UniqueConstraint("asset_id", "ordinal", name="uq_portal_column_ordinal"),
        PORTAL_TABLE_ARGS,
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    asset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{PORTAL_SCHEMA}.assets.id")
    )
    ordinal: Mapped[int]
    name: Mapped[str] = mapped_column(String(256))
    data_type: Mapped[str] = mapped_column(String(256))
    nullable: Mapped[bool] = mapped_column(default=True)
    description: Mapped[Optional[str]] = mapped_column(Text())


class PortalAssetSnapshotDbModel(Base):
    __tablename__ = "asset_snapshots"
    __table_args__ = (
        Index("ix_portal_snapshots_asset_time", "asset_id", "snapshot_at"),
        PORTAL_TABLE_ARGS,
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    asset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{PORTAL_SCHEMA}.assets.id")
    )
    snapshot_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True))
    table_bytes: Mapped[Optional[int]] = mapped_column(BigInteger())
    index_bytes: Mapped[Optional[int]] = mapped_column(BigInteger())
    total_bytes: Mapped[Optional[int]] = mapped_column(BigInteger())
    row_estimate: Mapped[Optional[int]] = mapped_column(BigInteger())
    object_count: Mapped[Optional[int]] = mapped_column(BigInteger())
    structure_hash: Mapped[Optional[str]] = mapped_column(String(128))


class PortalRelationshipDbModel(Base):
    __tablename__ = "relationships"
    __table_args__ = (
        UniqueConstraint(
            "from_asset_id",
            "to_asset_id",
            "relationship_type",
            name="uq_portal_relationship",
        ),
        Index("ix_portal_rel_from", "from_asset_id"),
        Index("ix_portal_rel_to", "to_asset_id"),
        PORTAL_TABLE_ARGS,
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    from_asset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{PORTAL_SCHEMA}.assets.id")
    )
    to_asset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{PORTAL_SCHEMA}.assets.id")
    )
    relationship_type: Mapped[str] = mapped_column(String(64))
    source_provider: Mapped[str] = mapped_column(String(64))
    native_id: Mapped[Optional[str]] = mapped_column(String(256))
    attributes: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)


class PortalChangeEventDbModel(Base):
    __tablename__ = "change_events"
    __table_args__ = (
        Index("ix_portal_changes_asset_time", "asset_id", "detected_at"),
        Index("ix_portal_changes_type_time", "change_type", "detected_at"),
        PORTAL_TABLE_ARGS,
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    asset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{PORTAL_SCHEMA}.assets.id")
    )
    detected_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True))
    change_type: Mapped[str] = mapped_column(String(64))
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)


class PortalDiscoveryDiagnosticDbModel(Base):
    __tablename__ = "discovery_diagnostics"
    __table_args__ = (PORTAL_TABLE_ARGS,)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    asset_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{PORTAL_SCHEMA}.assets.id")
    )
    detected_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True))
    severity: Mapped[str] = mapped_column(String(32))
    code: Mapped[str] = mapped_column(String(64))
    message: Mapped[str] = mapped_column(Text())
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)


class PortalCollectionRunDbModel(Base):
    __tablename__ = "collection_runs"
    __table_args__ = (
        Index("ix_portal_runs_name_time", "collector_name", "started_at"),
        PORTAL_TABLE_ARGS,
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    collector_name: Mapped[str] = mapped_column(String(64))
    started_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(32))
    message: Mapped[Optional[str]] = mapped_column(Text())
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
