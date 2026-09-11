from pathlib import Path

from fastapi import APIRouter, HTTPException, status

# В Docker-образе version.txt из корня проекта копируется в /app.
VERSION_FILE_PATH = Path("/app/version.txt")

system_router = APIRouter(prefix="/api/system", tags=["system"])


@system_router.get("/version", response_model=str)
def get_version() -> str:
    """Версия приложения: содержимое version.txt из корня проекта."""
    if not VERSION_FILE_PATH.is_file():
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="version.txt not found",
        )
    return VERSION_FILE_PATH.read_text(encoding="utf-8").strip()
