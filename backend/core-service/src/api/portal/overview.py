from fastapi import APIRouter, Depends

from api.portal.dto import (
    AssetCounts,
    OverviewResponse,
    RecentChanges,
    SchemaStorageRow,
    StorageTotals,
    change_item,
    freshness_items,
)
from domains.catalog.runtime import get_overview_service, get_portal_store
from domains.catalog.services.overview_service import OverviewService

overview_router = APIRouter()


@overview_router.get("/overview", response_model=OverviewResponse, operation_id="getOverview")
def get_overview(service: OverviewService = Depends(get_overview_service)) -> OverviewResponse:
    payload = service.get_overview()
    store = get_portal_store()
    return OverviewResponse(
        asset_counts=AssetCounts.model_validate(payload["asset_counts"]),
        storage_totals=StorageTotals.model_validate(payload["storage_totals"]),
        recent_changes=RecentChanges(
            total=payload["recent_changes"]["total"],
            added=payload["recent_changes"]["added"],
            changed=payload["recent_changes"]["changed"],
            removed=payload["recent_changes"]["removed"],
            items=[
                change_item(item, store.get_asset(item.asset_id))
                for item in payload["recent_changes"]["items"]
            ],
        ),
        collector_freshness=freshness_items(payload["collector_freshness"]),
        storage_by_schema=[SchemaStorageRow.model_validate(row) for row in payload["storage_by_schema"]],
    )
