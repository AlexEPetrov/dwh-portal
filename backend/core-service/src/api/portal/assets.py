from __future__ import annotations

import datetime
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from api.portal.dto import (
    AssetDetailResponse,
    AssetListResponse,
    ColumnListResponse,
    LineageResponse,
    LineageRootsResponse,
    LoadFileItem,
    LoadFileListResponse,
    RecentLoadFileItem,
    RecentLoadFileListResponse,
    UnresolvedTarget,
    asset_list_item,
    column_item,
    display_name_for,
    freshness_items,
    lineage_edge,
    lineage_node,
    snapshot_metrics,
    source_files_for,
)
from domains.catalog.models import AssetQuery, AssetStatus, AssetType
from domains.catalog.runtime import (
    get_asset_service,
    get_collection_status_service,
    get_extraction_load_service,
    get_lineage_service,
    get_portal_settings,
    get_portal_store,
)
from domains.catalog.services.asset_service import AssetService
from domains.catalog.services.collection_status_service import CollectionStatusService
from domains.catalog.services.extraction_load_service import ExtractionLoadService
from domains.catalog.services.lineage_service import LineageService

assets_router = APIRouter()


@assets_router.get(
    "/loads/recent", response_model=RecentLoadFileListResponse, operation_id="listRecentLoads"
)
def list_recent_loads(
    service: Annotated[ExtractionLoadService, Depends(get_extraction_load_service)],
    limit: int = Query(default=10, ge=1, le=50),
) -> RecentLoadFileListResponse:
    """Read recent log files independently from the snapshot-only overview."""
    payload = service.list_recent_loads(limit)
    return RecentLoadFileListResponse(
        items=[RecentLoadFileItem(**vars(item)) for item in payload.items],
        available=payload.available,
        limit=limit,
        has_more=payload.has_more,
    )


def _parse_asset_types(raw: str | None) -> list[AssetType] | None:
    if not raw:
        return None
    values = [part.strip() for part in raw.split(",") if part.strip()]
    if not values:
        return None
    return [AssetType(value) for value in values]


@assets_router.get(
    "/lineage/roots", response_model=LineageRootsResponse, operation_id="listLineageRoots"
)
def list_lineage_roots(
    service: Annotated[LineageService, Depends(get_lineage_service)],
    status_service: Annotated[CollectionStatusService, Depends(get_collection_status_service)],
) -> LineageRootsResponse:
    payload = service.list_roots()
    counts = payload.get("counts") or {}
    return LineageRootsResponse(
        nodes=[lineage_node(node, counts=counts.get(node.id)) for node in payload["nodes"]],
        edges=[lineage_edge(edge) for edge in payload["edges"]],
        unresolved_targets=[
            UnresolvedTarget.model_validate(item) for item in payload["unresolved_targets"]
        ],
        collector_freshness=freshness_items(status_service.list_status()),
    )


@assets_router.get("/assets", response_model=AssetListResponse, operation_id="listAssets")
def list_assets(
    service: Annotated[AssetService, Depends(get_asset_service)],
    status_service: Annotated[CollectionStatusService, Depends(get_collection_status_service)],
    q: str | None = None,
    database: str | None = None,
    schema: str | None = Query(default=None, alias="schema"),
    type: str | None = Query(
        default=None,
        alias="type",
        description="Asset type, or comma-separated types (TABLE,VIEW).",
    ),
    source: str | None = None,
    status: AssetStatus = AssetStatus.ACTIVE,
    changed_since: datetime.datetime | None = None,
    sort: str = "qualified_name",
    page: int = Query(default=1, ge=1),
    page_size: int | None = Query(default=None, ge=1),
) -> AssetListResponse:
    settings = get_portal_settings()
    resolved_page_size = min(page_size or settings.default_page_size, settings.max_page_size)
    asset_types = _parse_asset_types(type)
    query = AssetQuery(
        q=q,
        database=database,
        schema_name=schema,
        asset_type=asset_types[0] if asset_types and len(asset_types) == 1 else None,
        asset_types=asset_types,
        source=source,
        status=status,
        changed_since=changed_since,
        sort=sort,
        page=page,
        page_size=resolved_page_size,
    )
    rows, total = service.list_page(query)
    mapped = [asset_list_item(row.asset, row.snapshot, row.last_changed_at) for row in rows]
    return AssetListResponse(
        items=mapped,
        total=total,
        page=page,
        page_size=resolved_page_size,
        collector_freshness=freshness_items(status_service.list_status()),
    )


@assets_router.get(
    "/assets/{asset_id}", response_model=AssetDetailResponse, operation_id="getAsset"
)
def get_asset(
    asset_id: uuid.UUID,
    service: Annotated[AssetService, Depends(get_asset_service)],
    status_service: Annotated[CollectionStatusService, Depends(get_collection_status_service)],
) -> AssetDetailResponse:
    asset = service.get_asset(asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="Asset not found")
    snapshot = get_portal_store().latest_snapshot(asset.id)
    return AssetDetailResponse(
        id=asset.id,
        asset_type=asset.asset_type.value,
        qualified_name=asset.qualified_name,
        name=asset.name,
        display_name=display_name_for(asset),
        description=asset.description,
        database=asset.attributes.get("database"),
        schema_name=asset.attributes.get("schema"),
        source_provider=asset.source_provider,
        native_id=asset.native_id,
        status=asset.status.value,
        first_seen_at=asset.first_seen_at,
        last_seen_at=asset.last_seen_at,
        attributes={
            key: value
            for key, value in asset.attributes.items()
            if key not in {"previous_name", "previous_description"}
        },
        metrics=snapshot_metrics(snapshot),
        collector_freshness=freshness_items(status_service.list_status()),
        source_files=source_files_for(asset),
    )


@assets_router.get(
    "/assets/{asset_id}/columns", response_model=ColumnListResponse, operation_id="getAssetColumns"
)
def get_asset_columns(
    asset_id: uuid.UUID,
    service: Annotated[AssetService, Depends(get_asset_service)],
) -> ColumnListResponse:
    if service.get_asset(asset_id) is None:
        raise HTTPException(status_code=404, detail="Asset not found")
    return ColumnListResponse(
        items=[column_item(column) for column in service.get_columns(asset_id)]
    )


@assets_router.get(
    "/assets/{asset_id}/lineage", response_model=LineageResponse, operation_id="getAssetLineage"
)
def get_asset_lineage(
    asset_id: uuid.UUID,
    service: Annotated[LineageService, Depends(get_lineage_service)],
    status_service: Annotated[CollectionStatusService, Depends(get_collection_status_service)],
) -> LineageResponse:
    payload = service.get_lineage(asset_id)
    if payload["asset"] is None:
        raise HTTPException(status_code=404, detail="Asset not found")
    return LineageResponse(
        asset_id=asset_id,
        nodes=[lineage_node(node) for node in payload["nodes"]],
        edges=[lineage_edge(edge) for edge in payload["edges"]],
        unresolved_targets=[
            UnresolvedTarget.model_validate(item) for item in payload["unresolved_targets"]
        ],
        collector_freshness=freshness_items(status_service.list_status()),
    )


@assets_router.get(
    "/assets/{asset_id}/loads", response_model=LoadFileListResponse, operation_id="listAssetLoads"
)
def list_asset_loads(
    asset_id: uuid.UUID,
    service: Annotated[ExtractionLoadService, Depends(get_extraction_load_service)],
    page: int = Query(default=1, ge=1),
    page_size: int | None = Query(default=None, ge=1),
    include_total: bool = Query(default=True),
) -> LoadFileListResponse:
    settings = get_portal_settings()
    resolved_page_size = min(page_size or settings.default_page_size, settings.max_page_size)
    payload = service.list_loads(asset_id, page, resolved_page_size, include_total=include_total)
    if payload is None:
        raise HTTPException(status_code=404, detail="Asset not found")
    return LoadFileListResponse(
        items=[
            LoadFileItem(
                id=item.id,
                file_name=item.file_name,
                loaded_at=item.loaded_at,
                status=item.status,
                file_size=item.file_size,
                checksum=item.checksum,
                load_duration_sec=item.load_duration_sec,
                doc_date_actual=item.doc_date_actual,
            )
            for item in payload.items
        ],
        total=payload.total,
        page=page,
        page_size=resolved_page_size,
        available=payload.available,
        has_more=payload.has_more,
    )
