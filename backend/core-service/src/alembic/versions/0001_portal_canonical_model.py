"""Create portal canonical snapshot tables in sol_dwh_portal (code-first).

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

SCHEMA = "sol_dwh_portal"


def upgrade() -> None:
    op.execute(sa.schema.CreateSchema(SCHEMA, if_not_exists=True))

    op.create_table(
        "portal_assets",
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
        schema=SCHEMA,
    )
    op.create_index("ix_portal_assets_type", "portal_assets", ["asset_type"], schema=SCHEMA)
    op.create_index("ix_portal_assets_qualified_name", "portal_assets", ["qualified_name"], schema=SCHEMA)
    op.create_index("ix_portal_assets_deleted_at", "portal_assets", ["deleted_at"], schema=SCHEMA)

    op.create_table(
        "portal_asset_columns",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("asset_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=256), nullable=False),
        sa.Column("data_type", sa.String(length=256), nullable=False),
        sa.Column("nullable", sa.Boolean(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["asset_id"], [f"{SCHEMA}.portal_assets.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("asset_id", "ordinal", name="uq_portal_column_ordinal"),
        schema=SCHEMA,
    )

    op.create_table(
        "portal_asset_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("asset_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("snapshot_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("table_bytes", sa.BigInteger(), nullable=True),
        sa.Column("index_bytes", sa.BigInteger(), nullable=True),
        sa.Column("total_bytes", sa.BigInteger(), nullable=True),
        sa.Column("row_estimate", sa.BigInteger(), nullable=True),
        sa.Column("object_count", sa.BigInteger(), nullable=True),
        sa.Column("structure_hash", sa.String(length=128), nullable=True),
        sa.ForeignKeyConstraint(["asset_id"], [f"{SCHEMA}.portal_assets.id"]),
        sa.PrimaryKeyConstraint("id"),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_portal_snapshots_asset_time",
        "portal_asset_snapshots",
        ["asset_id", "snapshot_at"],
        schema=SCHEMA,
    )

    op.create_table(
        "portal_relationships",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("from_asset_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("to_asset_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("relationship_type", sa.String(length=64), nullable=False),
        sa.Column("source_provider", sa.String(length=64), nullable=False),
        sa.Column("native_id", sa.String(length=256), nullable=True),
        sa.Column("attributes", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.ForeignKeyConstraint(["from_asset_id"], [f"{SCHEMA}.portal_assets.id"]),
        sa.ForeignKeyConstraint(["to_asset_id"], [f"{SCHEMA}.portal_assets.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "from_asset_id",
            "to_asset_id",
            "relationship_type",
            name="uq_portal_relationship",
        ),
        schema=SCHEMA,
    )
    op.create_index("ix_portal_rel_from", "portal_relationships", ["from_asset_id"], schema=SCHEMA)
    op.create_index("ix_portal_rel_to", "portal_relationships", ["to_asset_id"], schema=SCHEMA)

    op.create_table(
        "portal_change_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("asset_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("change_type", sa.String(length=64), nullable=False),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.ForeignKeyConstraint(["asset_id"], [f"{SCHEMA}.portal_assets.id"]),
        sa.PrimaryKeyConstraint("id"),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_portal_changes_asset_time",
        "portal_change_events",
        ["asset_id", "detected_at"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_portal_changes_type_time",
        "portal_change_events",
        ["change_type", "detected_at"],
        schema=SCHEMA,
    )

    op.create_table(
        "portal_discovery_diagnostics",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("asset_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("severity", sa.String(length=32), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.ForeignKeyConstraint(["asset_id"], [f"{SCHEMA}.portal_assets.id"]),
        sa.PrimaryKeyConstraint("id"),
        schema=SCHEMA,
    )

    op.create_table(
        "portal_collection_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("collector_name", sa.String(length=64), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_portal_runs_name_time",
        "portal_collection_runs",
        ["collector_name", "started_at"],
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_index("ix_portal_runs_name_time", table_name="portal_collection_runs", schema=SCHEMA)
    op.drop_table("portal_collection_runs", schema=SCHEMA)
    op.drop_table("portal_discovery_diagnostics", schema=SCHEMA)
    op.drop_index("ix_portal_changes_type_time", table_name="portal_change_events", schema=SCHEMA)
    op.drop_index("ix_portal_changes_asset_time", table_name="portal_change_events", schema=SCHEMA)
    op.drop_table("portal_change_events", schema=SCHEMA)
    op.drop_index("ix_portal_rel_to", table_name="portal_relationships", schema=SCHEMA)
    op.drop_index("ix_portal_rel_from", table_name="portal_relationships", schema=SCHEMA)
    op.drop_table("portal_relationships", schema=SCHEMA)
    op.drop_index("ix_portal_snapshots_asset_time", table_name="portal_asset_snapshots", schema=SCHEMA)
    op.drop_table("portal_asset_snapshots", schema=SCHEMA)
    op.drop_table("portal_asset_columns", schema=SCHEMA)
    op.drop_index("ix_portal_assets_deleted_at", table_name="portal_assets", schema=SCHEMA)
    op.drop_index("ix_portal_assets_qualified_name", table_name="portal_assets", schema=SCHEMA)
    op.drop_index("ix_portal_assets_type", table_name="portal_assets", schema=SCHEMA)
    op.drop_table("portal_assets", schema=SCHEMA)
