from __future__ import annotations

import importlib
from typing import Any

from domains.catalog.providers.lineage import (
    STORAGE_TARGET_TYPES,
    LoaderMetadata,
    LoaderTarget,
)


def parse_loader_metadata(payload: dict[str, Any], *, default_name: str) -> LoaderMetadata:
    writes = [_parse_target(item) for item in payload.get("writes_to") or [] if _parse_target(item)]
    reads = [_parse_target(item) for item in payload.get("reads_from") or [] if _parse_target(item)]
    return LoaderMetadata(
        schema_version=str(payload.get("schema_version") or "1.0"),
        name=str(payload.get("name") or default_name),
        description=payload.get("description"),
        writes_to=writes,
        reads_from=reads,
        metadata_status="OK",
    )


def _parse_target(item: Any, *, allow_derived_from: bool = True) -> LoaderTarget | None:
    if not isinstance(item, dict):
        return None
    target_type = str(item.get("type") or "table").lower()
    if target_type in STORAGE_TARGET_TYPES:
        path = item.get("path") or item.get("name")
        if not path:
            return None
        return LoaderTarget(type=target_type, path=str(path))

    if not item.get("database") or not item.get("schema") or not item.get("name"):
        return None
    derived_from = None
    raw_derived = item.get("derived_from") if allow_derived_from else None
    if isinstance(raw_derived, dict):
        derived_from = _parse_target(raw_derived, allow_derived_from=False)
    return LoaderTarget(
        type=target_type,
        database=str(item["database"]),
        schema=str(item["schema"]),
        name=str(item["name"]),
        derived_from=derived_from,
    )


def resolve_python_metadata(module_name: str, default_name: str) -> LoaderMetadata:
    """Call module-level get_metadata() without instantiating a loader class."""
    try:
        module = importlib.import_module(module_name)
    except Exception as exc:
        return LoaderMetadata(
            schema_version="1.0",
            name=default_name,
            metadata_status="FAILED",
            diagnostic={"code": "PYTHON_IMPORT_FAILED", "message": str(exc), "module": module_name},
        )
    getter = getattr(module, "get_metadata", None)
    if getter is None:
        return LoaderMetadata(
            schema_version="1.0",
            name=default_name,
            metadata_status="MISSING",
            diagnostic={
                "code": "METADATA_MISSING",
                "message": "get_metadata() is not implemented",
                "module": module_name,
            },
        )
    try:
        payload = getter()
    except Exception as exc:
        return LoaderMetadata(
            schema_version="1.0",
            name=default_name,
            metadata_status="FAILED",
            diagnostic={"code": "METADATA_CALL_FAILED", "message": str(exc), "module": module_name},
        )
    if not isinstance(payload, dict):
        return LoaderMetadata(
            schema_version="1.0",
            name=default_name,
            metadata_status="INVALID",
            diagnostic={"code": "METADATA_INVALID", "message": "get_metadata() must return a dict"},
        )
    return parse_loader_metadata(payload, default_name=default_name)
