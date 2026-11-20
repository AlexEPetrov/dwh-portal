from contextlib import asynccontextmanager

from fastapi import FastAPI

from api.auth import auth_router
from api.portal import portal_router
from domains.catalog.db_targets import log_database_targets
from infrastructure.db.migration_check import ensure_portal_startup_migrations_current


@asynccontextmanager
async def lifespan(_app: FastAPI):
    log_database_targets()
    ensure_portal_startup_migrations_current()
    yield


app = FastAPI(
    title="DWH Portal",
    description="Portal API for catalog, storage, lineage and change snapshots.",
    lifespan=lifespan,
)

app.include_router(auth_router)
app.include_router(portal_router)
