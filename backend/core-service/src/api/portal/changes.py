from __future__ import annotations

import datetime
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query

from api.portal.dto import ChangeDetailResponse, ChangeListResponse, change_item, freshness_items
from domains.catalog.models import ChangeQuery, ChangeType
from domains.catalog.runtime import get_change_service, get_collection_status_service, get_portal_store
from domains.catalog.services.change_service import ChangeService
from domains.catalog.services.collection_status_service import CollectionStatusService

changes_router = APIRouter()


@changes_router.get("/changes", response_model=ChangeListResponse, operation_id="listChanges")
def list_changes(
    change_type: ChangeType | None = None,
    since: datetime.datetime | None = None,
    until: datetime.datetime | None = None,
    asset_id: uuid.UUID | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    service: ChangeService = Depends(get_change_service),
    status_service: CollectionStatusService = Depends(get_collection_status_service),
) -> ChangeListResponse:
    items, total = service.list_changes(
        ChangeQuery(
            change_type=change_type,
            since=since,
            until=until,
            asset_id=asset_id,
            page=page,
            page_size=page_size,
        )
    )
    added = sum(1 for item in items if item.change_type == ChangeType.ADDED)
    removed = sum(1 for item in items if item.change_type == ChangeType.REMOVED)
    store = get_portal_store()
    return ChangeListResponse(
        items=[change_item(item, store.get_asset(item.asset_id)) for item in items],
        total=total,
        page=page,
        page_size=page_size,
        added=added,
        changed=len(items) - added - removed,
        removed=removed,
        collector_freshness=freshness_items(status_service.list_status()),
    )


@changes_router.get("/changes/{change_id}", response_model=ChangeDetailResponse, operation_id="getChange")
def get_change(
    change_id: uuid.UUID, service: ChangeService = Depends(get_change_service)
) -> ChangeDetailResponse:
    event = service.get_change(change_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Change not found")
    asset = get_portal_store().get_asset(event.asset_id)
    return ChangeDetailResponse(
        id=event.id,
        asset_id=event.asset_id,
        change_type=event.change_type.value,
        detected_at=event.detected_at,
        details=event.details,
        asset_qualified_name=asset.qualified_name if asset else None,
    )
