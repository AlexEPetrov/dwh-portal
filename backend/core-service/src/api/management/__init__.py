# Parent router for users
from fastapi import APIRouter

from api.management.scenarios import scenarios_router

management_router = APIRouter(prefix="/api/management", tags=["management"])

management_router.include_router(scenarios_router)
