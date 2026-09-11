from fastapi import status
from fastapi.responses import JSONResponse

from api.host import app
from infrastructure.services.health import (
    check_all,
)


@app.get("/health")
async def health_check():

    is_healthy, result = check_all()

    return JSONResponse(
        status_code=200 if is_healthy else status.HTTP_503_SERVICE_UNAVAILABLE, content=result
    )
