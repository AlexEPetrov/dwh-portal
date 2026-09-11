from fastapi import APIRouter, Depends

from api.portal.dto import CollectionStatusResponse, freshness_items
from domains.catalog.runtime import get_collection_status_service
from domains.catalog.services.collection_status_service import CollectionStatusService

collection_status_router = APIRouter()


@collection_status_router.get(
    "/collection-status",
    response_model=CollectionStatusResponse,
    operation_id="getCollectionStatus",
)
def get_collection_status(
    service: CollectionStatusService = Depends(get_collection_status_service),
) -> CollectionStatusResponse:
    return CollectionStatusResponse(items=freshness_items(service.list_status()))
