import datetime
from typing import Annotated

from fastapi import APIRouter, Depends

from api.portal.dto import (
    SchemaStorageRow,
    StorageHistoryPoint,
    StorageHistoryResponse,
    StorageObjectRow,
    StorageResponse,
    freshness_items,
)
from domains.catalog.runtime import get_collection_status_service, get_storage_service
from domains.catalog.services.collection_status_service import CollectionStatusService
from domains.catalog.services.storage_service import StorageService

storage_router = APIRouter()


@storage_router.get("/storage", response_model=StorageResponse, operation_id="getStorage")
def get_storage(
    service: Annotated[StorageService, Depends(get_storage_service)],
    status_service: Annotated[CollectionStatusService, Depends(get_collection_status_service)],
) -> StorageResponse:
    payload = service.current()
    return StorageResponse(
        as_of=payload["as_of"],
        table_bytes=payload["table_bytes"],
        index_bytes=payload["index_bytes"],
        total_bytes=payload["total_bytes"],
        by_schema=[SchemaStorageRow.model_validate(row) for row in payload["by_schema"]],
        largest_objects=[
            StorageObjectRow.model_validate(row) for row in payload["largest_objects"]
        ],
        collector_freshness=freshness_items(status_service.list_status()),
    )


@storage_router.get(
    "/storage/history", response_model=StorageHistoryResponse, operation_id="getStorageHistory"
)
def get_storage_history(
    service: Annotated[StorageService, Depends(get_storage_service)],
    status_service: Annotated[CollectionStatusService, Depends(get_collection_status_service)],
    since: datetime.datetime | None = None,
) -> StorageHistoryResponse:
    return StorageHistoryResponse(
        items=[StorageHistoryPoint.model_validate(row) for row in service.history(since)],
        collector_freshness=freshness_items(status_service.list_status()),
    )
