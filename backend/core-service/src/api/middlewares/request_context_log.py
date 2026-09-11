from uuid import uuid4

from starlette.middleware.base import RequestResponseEndpoint

from shared.request_manager import (
    correlation_id_ctx_var,
    request_id_ctx_var,
    get_correlation_id,
    get_request_id,
)

# CORRELATION_ID_CTX_KEY = 'correlation_id'
# REQUEST_ID_CTX_KEY = 'request_id'

# _correlation_id_ctx_var: ContextVar[str] = ContextVar(CORRELATION_ID_CTX_KEY, default=None)
# _request_id_ctx_var: ContextVar[str] = ContextVar(REQUEST_ID_CTX_KEY, default=None)


# def get_correlation_id() -> str:
#     return _correlation_id_ctx_var.get()


# def get_request_id() -> str:
#     return _request_id_ctx_var.get()

from api.host import app
from fastapi import Request


@app.middleware("http")
async def request_correlation_id(request: Request, call_next: RequestResponseEndpoint):

    correlation_id = correlation_id_ctx_var.set(
        request.headers.get("X-Correlation-ID", str(uuid4()))
    )
    request_id = request_id_ctx_var.set(str(uuid4()))

    response = await call_next(request)

    response.headers["X-Correlation-ID"] = get_correlation_id()
    response.headers["X-Request-ID"] = get_request_id()

    correlation_id_ctx_var.reset(correlation_id)
    request_id_ctx_var.reset(request_id)

    return response
