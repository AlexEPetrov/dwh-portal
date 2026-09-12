from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Body, Depends, Query
from fastapi.responses import JSONResponse

from api.portal.dto import CollectRequest, CollectResponse, CollectRunItem
from domains.catalog.runtime import get_collection_service
from domains.catalog.services.collection_service import CollectionService, CollectOptions

collect_router = APIRouter()


@collect_router.post(
    "/collect",
    response_model=CollectResponse,
    operation_id="runPortalCollect",
    responses={500: {"model": CollectResponse}},
)
def run_portal_collect(
    reset: bool = Query(False, description="Purge sol_dwh_portal snapshots before collecting"),
    airflow_lineage_mode: Literal["catalog", "code"] | None = Query(
        None,
        description="Airflow WRITES_TO matching: catalog (snapshot tables only) or code (DAG AST)",
    ),
    payload: CollectRequest | None = Body(default=None),
    service: CollectionService = Depends(get_collection_service),
) -> CollectResponse | JSONResponse:
    """Trigger snapshot collection. Intended for Airflow DAGs, not UI page loads."""
    if payload is not None:
        reset = payload.reset
        if payload.airflow_lineage_mode is not None:
            airflow_lineage_mode = payload.airflow_lineage_mode
    result = service.run(
        CollectOptions(reset=reset, airflow_lineage_mode=airflow_lineage_mode)
    )
    response = CollectResponse(
        reset=result.reset,
        airflow_lineage_mode=result.airflow_lineage_mode,
        failed=result.failed,
        runs={
            name: CollectRunItem(
                status=item.status, message=item.message, details=item.details
            )
            for name, item in result.runs.items()
        },
    )
    if response.failed:
        return JSONResponse(status_code=500, content=response.model_dump(mode="json"))
    return response
