from uuid import uuid4

from fastapi import FastAPI, Request
from starlette.middleware.base import RequestResponseEndpoint

from shared.request_context import (
    bind_request_ids,
    get_correlation_id,
    get_request_id,
    reset_request_ids,
)


def register(app: FastAPI) -> None:
    """Attach request correlation headers to the Portal FastAPI app."""

    @app.middleware("http")
    async def request_correlation_id(request: Request, call_next: RequestResponseEndpoint):
        correlation_token, request_token = bind_request_ids(
            correlation_id=request.headers.get("X-Correlation-ID", str(uuid4())),
            request_id=str(uuid4()),
        )
        response = await call_next(request)
        response.headers["X-Correlation-ID"] = get_correlation_id() or ""
        response.headers["X-Request-ID"] = get_request_id() or ""
        reset_request_ids(correlation_token, request_token)
        return response
