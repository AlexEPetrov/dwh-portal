from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, status
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from api.ai import ai_router
from api.auth import auth_router
from api.health import health_router
from api.middlewares.request_context_log import register as register_request_context
from api.portal import portal_router
from api.system import system_router
from domains.catalog.db_targets import log_database_targets
from infrastructure.db.migration_check import ensure_portal_migrations_current
from shared.nullables import require

tags_metadata = [
    {
        "name": "catalog",
        "description": "DWH Portal catalog, storage, lineage and change snapshots.",
    },
]


@asynccontextmanager
async def lifespan(_app: FastAPI):
    log_database_targets()
    ensure_portal_migrations_current()
    yield


app: FastAPI = FastAPI(openapi_tags=tags_metadata, lifespan=lifespan)

register_request_context(app)
app.mount("/static", StaticFiles(directory="src/api/static"), name="static")

app.include_router(health_router)
app.include_router(auth_router)
app.include_router(ai_router)
app.include_router(system_router)
app.include_router(portal_router)

WEB_DIST_DIR = Path("/app/frontend-dist")


@app.get("/swagger", include_in_schema=False)
async def custom_swagger_ui_html():
    return get_swagger_ui_html(
        openapi_url=require(app.openapi_url),
        title=app.title + " - Swagger UI",
        oauth2_redirect_url=app.swagger_ui_oauth2_redirect_url,
        swagger_js_url="/static/swagger-ui-bundle.js",
        swagger_css_url="/static/swagger-ui.css",
    )


@app.get("/favicon.ico", include_in_schema=False)
async def favicon_redirect():
    favicon_svg = WEB_DIST_DIR / "vite.svg"
    if favicon_svg.exists():
        return RedirectResponse(url="/vite.svg", status_code=307)
    return JSONResponse(status_code=404, content={"detail": "Not Found"})


@app.exception_handler(NotImplementedError)
async def not_implemented_handler(request: Request, exc: NotImplementedError):
    error_message = exc.args[0] if exc.args else "Функционал еще не реализован"
    return JSONResponse(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        content={"error": "NotImplemented", "message": error_message, "path": request.url.path},
    )


@app.get("/{full_path:path}", include_in_schema=False)
async def frontend_spa_fallback(full_path: str):
    if not WEB_DIST_DIR.exists():
        return JSONResponse(status_code=404, content={"detail": "Frontend build not found"})
    if (
        full_path.startswith("api/")
        or full_path.startswith("swagger")
        or full_path.startswith("docs")
    ):
        return JSONResponse(status_code=404, content={"detail": "Not Found"})

    requested_path = WEB_DIST_DIR / full_path
    if requested_path.exists() and requested_path.is_file():
        return FileResponse(requested_path)

    index_file = WEB_DIST_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return JSONResponse(status_code=404, content={"detail": "Frontend index not found"})
