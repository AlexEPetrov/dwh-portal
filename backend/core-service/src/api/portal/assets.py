from __future__ import annotations

import datetime
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query

from api.portal.dto import (
    AssetDetailResponse,
    AssetListResponse,
    ColumnListResponse,
    LineageResponse,
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
    get_lineage_service,
    get_portal_settings,
    get_portal_store,
)
from domains.catalog.services.asset_service import AssetService
from domains.catalog.services.collection_status_service import CollectionStatusService
from domains.catalog.services.lineage_service import LineageService

assets_router = APIRouter()


@assets_router.get("/assets", response_model=AssetListResponse, operation_id="listAssets")
def list_assets(
    q: str | None = None,
    database: str | None = None,
    schema: str | None = Query(default=None, alias="schema"),
    type: str | None = Query(default=None, alias="type"),
    source: str | None = None,
    status: AssetStatus = AssetStatus.ACTIVE,
    changed_since: datetime.datetime | None = None,
    sort: str = "qualified_name",
    page: int = Query(default=1, ge=1),
    page_size: int | None = Query(default=None, ge=1),
    service: AssetService = Depends(get_asset_service),
    status_service: CollectionStatusService = Depends(get_collection_status_service),
) -> AssetListResponse:
    settings = get_portal_settings()
    resolved_page_size = min(page_size or settings.default_page_size, settings.max_page_size)
    asset_type = AssetType(type) if type else None
    query = AssetQuery(
        q=q,
        database=database,
        schema_name=schema,
        asset_type=asset_type,
        source=source,
        status=status,
        changed_since=changed_since,
        sort=sort,
        page=page,
        page_size=resolved_page_size,
    )
    items, total = service.list_assets(query)
    store = get_portal_store()
    mapped = [
        asset_list_item(asset, store.latest_snapshot(asset.id), service.latest_change_at(asset.id))
        for asset in items
    ]
    return AssetListResponse(
        items=mapped,
        total=total,
        page=page,
        page_size=resolved_page_size,
        collector_freshness=freshness_items(status_service.list_status()),
    )


@assets_router.get("/assets/{asset_id}", response_model=AssetDetailResponse, operation_id="getAsset")
def get_asset(
    asset_id: uuid.UUID,
    service: AssetService = Depends(get_asset_service),
    status_service: CollectionStatusService = Depends(get_collection_status_service),
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
    asset_id: uuid.UUID, service: AssetService = Depends(get_asset_service)
) -> ColumnListResponse:
    if service.get_asset(asset_id) is None:
        raise HTTPException(status_code=404, detail="Asset not found")
    return ColumnListResponse(items=[column_item(column) for column in service.get_columns(asset_id)])


@assets_router.get(
    "/assets/{asset_id}/lineage", response_model=LineageResponse, operation_id="getAssetLineage"
)
def get_asset_lineage(
    asset_id: uuid.UUID,
    service: LineageService = Depends(get_lineage_service),
    status_service: CollectionStatusService = Depends(get_collection_status_service),
) -> LineageResponse:
    payload = service.get_lineage(asset_id)
    if payload["asset"] is None:
        raise HTTPException(status_code=404, detail="Asset not found")
    return LineageResponse(
        asset_id=asset_id,
        nodes=[lineage_node(node) for node in payload["nodes"]],
        edges=[lineage_edge(edge) for edge in payload["edges"]],
        unresolved_targets=[UnresolvedTarget.model_validate(item) for item in payload["unresolved_targets"]],
        collector_freshness=freshness_items(status_service.list_status()),
    )
