"""Create portal canonical snapshot tables.

Revision ID: 0001_portal
Revises:
Create Date: 2026-09-06
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_portal"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(sa.schema.CreateSchema("portal", if_not_exists=True))
    op.create_table(
        "assets",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("asset_type", sa.String(length=64), nullable=False),
        sa.Column("qualified_name", sa.String(length=512), nullable=False),
        sa.Column("name", sa.String(length=256), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("source_provider", sa.String(length=64), nullable=False),
        sa.Column("native_id", sa.String(length=256), nullable=True),
        sa.Column("identity_key", sa.String(length=512), nullable=False),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attributes", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_provider", "identity_key", name="uq_portal_asset_identity"),
        schema="portal",
    )
    op.create_index("ix_portal_assets_type", "assets", ["asset_type"], schema="portal")
    op.create_index("ix_portal_assets_qualified_name", "assets", ["qualified_name"], schema="portal")
    op.create_index("ix_portal_assets_deleted_at", "assets", ["deleted_at"], schema="portal")

    op.create_table(
        "asset_columns",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("asset_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=256), nullable=False),
        sa.Column("data_type", sa.String(length=256), nullable=False),
        sa.Column("nullable", sa.Boolean(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["asset_id"], ["portal.assets.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("asset_id", "ordinal", name="uq_portal_column_ordinal"),
        schema="portal",
    )
    op.create_table(
        "asset_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("asset_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("snapshot_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("table_bytes", sa.BigInteger(), nullable=True),
        sa.Column("index_bytes", sa.BigInteger(), nullable=True),
        sa.Column("total_bytes", sa.BigInteger(), nullable=True),
        sa.Column("row_estimate", sa.BigInteger(), nullable=True),
        sa.Column("object_count", sa.BigInteger(), nullable=True),
        sa.Column("structure_hash", sa.String(length=128), nullable=True),
        sa.ForeignKeyConstraint(["asset_id"], ["portal.assets.id"]),
        sa.PrimaryKeyConstraint("id"),
        schema="portal",
    )
    op.create_index(
        "ix_portal_snapshots_asset_time",
        "asset_snapshots",
        ["asset_id", "snapshot_at"],
        schema="portal",
    )
    op.create_table(
        "relationships",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("from_asset_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("to_asset_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("relationship_type", sa.String(length=64), nullable=False),
        sa.Column("source_provider", sa.String(length=64), nullable=False),
        sa.Column("native_id", sa.String(length=256), nullable=True),
        sa.Column("attributes", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.ForeignKeyConstraint(["from_asset_id"], ["portal.assets.id"]),
        sa.ForeignKeyConstraint(["to_asset_id"], ["portal.assets.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "from_asset_id", "to_asset_id", "relationship_type", name="uq_portal_relationship"
        ),
        schema="portal",
    )
    op.create_index("ix_portal_rel_from", "relationships", ["from_asset_id"], schema="portal")
    op.create_index("ix_portal_rel_to", "relationships", ["to_asset_id"], schema="portal")
    op.create_table(
        "change_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("asset_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("change_type", sa.String(length=64), nullable=False),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.ForeignKeyConstraint(["asset_id"], ["portal.assets.id"]),
        sa.PrimaryKeyConstraint("id"),
        schema="portal",
    )
    op.create_index(
        "ix_portal_changes_asset_time",
        "change_events",
        ["asset_id", "detected_at"],
        schema="portal",
    )
    op.create_table(
        "discovery_diagnostics",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("asset_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("severity", sa.String(length=32), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.ForeignKeyConstraint(["asset_id"], ["portal.assets.id"]),
        sa.PrimaryKeyConstraint("id"),
        schema="portal",
    )
    op.create_table(
        "collection_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("collector_name", sa.String(length=64), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        schema="portal",
    )
    op.create_index(
        "ix_portal_runs_name_time",
        "collection_runs",
        ["collector_name", "started_at"],
        schema="portal",
    )


def downgrade() -> None:
    op.drop_table("collection_runs", schema="portal")
    op.drop_table("discovery_diagnostics", schema="portal")
    op.drop_table("change_events", schema="portal")
    op.drop_table("relationships", schema="portal")
    op.drop_table("asset_snapshots", schema="portal")
    op.drop_table("asset_columns", schema="portal")
    op.drop_table("assets", schema="portal")
    op.execute("DROP SCHEMA IF EXISTS portal")
