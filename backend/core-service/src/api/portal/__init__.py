from fastapi import APIRouter

from api.portal.assets import assets_router
from api.portal.changes import changes_router
from api.portal.collect import collect_router
from api.portal.collection_status import collection_status_router
from api.portal.overview import overview_router
from api.portal.storage import storage_router

portal_router = APIRouter(prefix="/api/v1", tags=["catalog"])
portal_router.include_router(overview_router)
portal_router.include_router(assets_router)
portal_router.include_router(storage_router)
portal_router.include_router(changes_router)
portal_router.include_router(collection_status_router)
portal_router.include_router(collect_router)
