"""Request-scoped correlation identifiers for HTTP logging."""

from contextvars import ContextVar
from uuid import uuid4

_correlation_id: ContextVar[str | None] = ContextVar("correlation_id", default=None)
_request_id: ContextVar[str | None] = ContextVar("request_id", default=None)


def get_correlation_id() -> str | None:
    return _correlation_id.get()


def get_request_id() -> str | None:
    return _request_id.get()


def bind_request_ids(*, correlation_id: str | None = None, request_id: str | None = None):
    """Set request ids for the current context. Returns tokens for reset."""
    return (
        _correlation_id.set(correlation_id or str(uuid4())),
        _request_id.set(request_id or str(uuid4())),
    )


def reset_request_ids(correlation_token, request_token) -> None:
    _correlation_id.reset(correlation_token)
    _request_id.reset(request_token)
