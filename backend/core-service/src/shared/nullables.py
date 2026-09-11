from typing import TypeVar

T = TypeVar("T")


def require(value: T | None, default: T | None = None, msg: str = "Unexpected None") -> T:
    if value is not None:
        return value
    if default is not None:  # is not None! include 0, etc.
        return default
    raise ValueError(msg)
