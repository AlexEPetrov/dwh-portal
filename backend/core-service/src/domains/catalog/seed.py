from __future__ import annotations

import datetime
import uuid

from domains.catalog.identity import (
    compute_structure_hash,
    data_source_identity,
    extraction_source_identity,
    process_identity,
    relation_identity,
    schema_identity,
    storage_location_identity,
)
from domains.catalog.models import (
    Asset,
    AssetColumn,
    AssetSnapshot,
    AssetType,
    ChangeEvent,
    ChangeType,
    CollectionRun,
    CollectorStatus,
    Relationship,
    RelationshipType,
)
from domains.catalog.repositories.ports import PortalStore

DEMO_NOW = datetime.datetime(2026, 9, 6, 2, 15, tzinfo=datetime.timezone.utc)
CONNECTION = "dwh"
PROVIDER_PG = "postgres"
PROVIDER_REG = "extraction_registry"


def _asset(
    *,
    asset_id: uuid.UUID,
    asset_type: AssetType,
    qualified_name: str,
    name: str,
    identity_key: str,
    source_provider: str,
    description: str | None = None,
    native_id: str | None = None,
    attributes: dict | None = None,
    first_seen_at: datetime.datetime | None = None,
) -> Asset:
    seen = first_seen_at or DEMO_NOW
    return Asset(
        id=asset_id,
        asset_type=asset_type,
        qualified_name=qualified_name,
        name=name,
        description=description,
        source_provider=source_provider,
        native_id=native_id,
        identity_key=identity_key,
        first_seen_at=seen,
        last_seen_at=DEMO_NOW,
        attributes=attributes or {},
    )


def _columns(asset_id: uuid.UUID, rows: list[tuple[str, str, bool, str]]) -> list[AssetColumn]:
    return [
        AssetColumn(
            asset_id=asset_id,
            ordinal=index,
            name=name,
            data_type=data_type,
            nullable=nullable,
            description=description,
        )
        for index, (name, data_type, nullable, description) in enumerate(rows, start=1)
    ]


def seed_demo_catalog(store: PortalStore) -> None:
    """Populate a representative Phase 1 snapshot used by the prototype UI."""
    if not store.is_empty():
        return

    database_id = uuid.UUID("11111111-1111-1111-1111-111111111111")
    schemas = {
        "raw": uuid.UUID("22222222-2222-2222-2222-222222222201"),
        "dwh": uuid.UUID("22222222-2222-2222-2222-222222222202"),
        "history": uuid.UUID("22222222-2222-2222-2222-222222222203"),
        "stage": uuid.UUID("22222222-2222-2222-2222-222222222204"),
        "mart": uuid.UUID("22222222-2222-2222-2222-222222222205"),
    }
    tables = {
        "raw.ice_brent": uuid.UUID("33333333-3333-3333-3333-333333333301"),
        "raw.ice_options": uuid.UUID("33333333-3333-3333-3333-333333333302"),
        "dwh.market_prices": uuid.UUID("33333333-3333-3333-3333-333333333303"),
        "dwh.instruments": uuid.UUID("33333333-3333-3333-3333-333333333304"),
        "history.transactions": uuid.UUID("33333333-3333-3333-3333-333333333305"),
        "stage.old_ice_prices": uuid.UUID("33333333-3333-3333-3333-333333333306"),
        "mart.commodity_prices": uuid.UUID("33333333-3333-3333-3333-333333333307"),
    }
    source_id = uuid.UUID("44444444-4444-4444-4444-444444444401")
    extraction_id = uuid.UUID("44444444-4444-4444-4444-444444444402")
    storage_id = uuid.UUID("44444444-4444-4444-4444-444444444403")
    process_id = uuid.UUID("44444444-4444-4444-4444-444444444404")

    db_qn, db_key = "dwh", f"db:{CONNECTION}:dwh"
    store.upsert_asset(
        _asset(
            asset_id=database_id,
            asset_type=AssetType.DATABASE,
            qualified_name=db_qn,
            name="dwh",
            identity_key=db_key,
            source_provider=PROVIDER_PG,
            description="DWH PostgreSQL",
            attributes={"database": "dwh", "connection_identity": CONNECTION},
        )
    )

    for schema_name, schema_id in schemas.items():
        qualified_name, identity_key = schema_identity(CONNECTION, "dwh", schema_name)
        store.upsert_asset(
            _asset(
                asset_id=schema_id,
                asset_type=AssetType.SCHEMA,
                qualified_name=qualified_name,
                name=schema_name,
                identity_key=identity_key,
                source_provider=PROVIDER_PG,
                attributes={"database": "dwh", "schema": schema_name},
            )
        )
        store.upsert_relationship(
            Relationship(
                from_asset_id=database_id,
                to_asset_id=schema_id,
                relationship_type=RelationshipType.CONTAINS,
                source_provider=PROVIDER_PG,
            )
        )

    table_specs: list[tuple[str, str, str, str, AssetType, list[tuple[str, str, bool, str]], dict]] = [
        (
            "raw.ice_brent",
            "raw",
            "ice_brent",
            "ICE Brent settlement landings",
            AssetType.TABLE,
            [
                ("trade_date", "date", False, "Trading date"),
                ("settlement_price", "numeric(18,6)", True, "Settlement price"),
                ("currency", "varchar(3)", True, "Currency"),
            ],
            {"table_bytes": 84 * 1024**3, "index_bytes": 12 * 1024**3, "row_estimate": 310_000_000},
        ),
        (
            "raw.ice_options",
            "raw",
            "ice_options",
            "New ICE options landing",
            AssetType.TABLE,
            [(f"col_{index}", "text", True, f"Column {index}") for index in range(1, 15)],
            {"table_bytes": 2 * 1024**3, "index_bytes": 400 * 1024**2, "row_estimate": 8_000_000},
        ),
        (
            "dwh.market_prices",
            "dwh",
            "market_prices",
            "Market prices and settlement values",
            AssetType.TABLE,
            [
                ("instrument_id", "bigint", False, "Instrument identifier"),
                ("trade_date", "date", False, "Trading date"),
                ("settlement_price", "numeric(18,6)", True, "Settlement price"),
                ("currency", "varchar(3)", True, "Currency"),
            ],
            {"table_bytes": 128 * 1024**3, "index_bytes": 31 * 1024**3, "row_estimate": 420_000_000},
        ),
        (
            "dwh.instruments",
            "dwh",
            "instruments",
            "Instrument master",
            AssetType.TABLE,
            [("instrument_id", "bigint", False, "Instrument identifier")],
            {"table_bytes": 31 * 1024**3, "index_bytes": 4 * 1024**3, "row_estimate": 82_000_000},
        ),
        (
            "history.transactions",
            "history",
            "transactions",
            "Historical transactions",
            AssetType.TABLE,
            [("txn_id", "bigint", False, "Transaction id")],
            {"table_bytes": 2_300 * 1024**3, "index_bytes": 200 * 1024**3, "row_estimate": 9_000_000_000},
        ),
        (
            "stage.old_ice_prices",
            "stage",
            "old_ice_prices",
            "Retired ICE prices",
            AssetType.TABLE,
            [("trade_date", "date", False, "Trading date")],
            {"table_bytes": 12 * 1024**3, "index_bytes": 1 * 1024**3, "row_estimate": 40_000_000},
        ),
        (
            "mart.commodity_prices",
            "mart",
            "commodity_prices",
            "Commodity price mart",
            AssetType.VIEW,
            [
                ("instrument_id", "bigint", False, "Instrument identifier"),
                ("trade_date", "date", False, "Trading date"),
            ],
            {},
        ),
    ]

    for key, schema_name, name, description, asset_type, column_rows, metrics in table_specs:
        asset_id = tables[key]
        qualified_name, identity_key = relation_identity(CONNECTION, "dwh", schema_name, name)
        asset = _asset(
            asset_id=asset_id,
            asset_type=asset_type,
            qualified_name=qualified_name,
            name=name,
            identity_key=identity_key,
            source_provider=PROVIDER_PG,
            description=description,
            attributes={"database": "dwh", "schema": schema_name, "display_name": f"{schema_name}.{name}"},
        )
        if key == "stage.old_ice_prices":
            asset.deleted_at = DEMO_NOW
        store.upsert_asset(asset)
        columns = _columns(asset_id, column_rows)
        store.replace_columns(asset_id, columns)
        store.upsert_relationship(
            Relationship(
                from_asset_id=schemas[schema_name],
                to_asset_id=asset_id,
                relationship_type=RelationshipType.CONTAINS,
                source_provider=PROVIDER_PG,
            )
        )
        if asset_type != AssetType.VIEW:
            store.add_snapshot(
                AssetSnapshot(
                    asset_id=asset_id,
                    snapshot_at=DEMO_NOW,
                    table_bytes=metrics.get("table_bytes"),
                    index_bytes=metrics.get("index_bytes"),
                    total_bytes=(metrics.get("table_bytes") or 0) + (metrics.get("index_bytes") or 0)
                    or None,
                    row_estimate=metrics.get("row_estimate"),
                    structure_hash=compute_structure_hash(asset_type, columns),
                )
            )

    ice_qn, ice_key = data_source_identity("ice-source")
    store.upsert_asset(
        _asset(
            asset_id=source_id,
            asset_type=AssetType.DATA_SOURCE,
            qualified_name=ice_qn,
            name="ICE",
            identity_key=ice_key,
            source_provider=PROVIDER_REG,
            description="ICE source system",
            native_id="ice-source",
        )
    )
    extraction_qn, extraction_key = extraction_source_identity("brent-doc")
    store.upsert_asset(
        _asset(
            asset_id=extraction_id,
            asset_type=AssetType.EXTRACTION_SOURCE,
            qualified_name=extraction_qn,
            name="Brent Settlement",
            identity_key=extraction_key,
            source_provider=PROVIDER_REG,
            description="Brent settlement document",
            native_id="brent-doc",
            attributes={"extract_source_type_id": 1, "is_active": True, "access_level": 1},
        )
    )
    storage_qn, storage_key = storage_location_identity("landing/ice/brent")
    store.upsert_asset(
        _asset(
            asset_id=storage_id,
            asset_type=AssetType.STORAGE_LOCATION,
            qualified_name=storage_qn,
            name="landing/ice/brent",
            identity_key=storage_key,
            source_provider=PROVIDER_REG,
            attributes={"path": "landing/ice/brent"},
        )
    )
    process_qn, process_key = process_identity("brent-doc", "0")
    store.upsert_asset(
        _asset(
            asset_id=process_id,
            asset_type=AssetType.PROCESS,
            qualified_name=process_qn,
            name="ice_brent_loader",
            identity_key=process_key,
            source_provider=PROVIDER_REG,
            attributes={"handler_type": "Python", "metadata_status": "OK", "lineage_status": "RESOLVED"},
        )
    )

    lineage_edges = [
        (source_id, extraction_id, RelationshipType.EXTRACTS_TO),
        (extraction_id, storage_id, RelationshipType.EXTRACTS_TO),
        (process_id, storage_id, RelationshipType.READS_FROM),
        (process_id, tables["raw.ice_brent"], RelationshipType.WRITES_TO),
        (tables["raw.ice_brent"], tables["dwh.market_prices"], RelationshipType.DERIVED_FROM),
    ]
    for from_id, to_id, rel_type in lineage_edges:
        store.upsert_relationship(
            Relationship(
                from_asset_id=from_id,
                to_asset_id=to_id,
                relationship_type=rel_type,
                source_provider=PROVIDER_REG,
            )
        )

    changes = [
        ChangeEvent(
            asset_id=tables["raw.ice_options"],
            detected_at=DEMO_NOW,
            change_type=ChangeType.ADDED,
            details={"summary": "New table, 14 columns"},
        ),
        ChangeEvent(
            asset_id=tables["dwh.market_prices"],
            detected_at=DEMO_NOW,
            change_type=ChangeType.STRUCTURE_CHANGED,
            details={"added": [{"name": "currency", "data_type": "varchar(3)", "nullable": True}]},
        ),
        ChangeEvent(
            asset_id=tables["stage.old_ice_prices"],
            detected_at=DEMO_NOW,
            change_type=ChangeType.REMOVED,
            details={"summary": "Retired landing table"},
        ),
    ]
    for event in changes:
        store.add_change(event)

    for collector_name, offset_minutes in (
        ("catalog", 3),
        ("storage", 2),
        ("extraction_registry", 1),
        ("changes", 0),
    ):
        started = DEMO_NOW - datetime.timedelta(minutes=offset_minutes)
        store.add_collection_run(
            CollectionRun(
                collector_name=collector_name,
                started_at=started,
                finished_at=started + datetime.timedelta(minutes=1),
                status=CollectorStatus.SUCCESS,
                message="Demo snapshot",
            )
        )
