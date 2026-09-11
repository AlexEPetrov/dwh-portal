from fastapi import FastAPI

from api.auth import auth_router
from api.portal import portal_router

app = FastAPI(
    title="DWH Portal",
    description="Portal API for catalog, storage, lineage and change snapshots.",
)

app.include_router(auth_router)
app.include_router(portal_router)
