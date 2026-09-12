from __future__ import annotations

import hashlib
import json
from typing import Any, Iterable

from domains.catalog.models import AssetColumn, AssetType


SECRET_ATTRIBUTE_KEYS = {
    "password",
    "passwd",
    "secret",
    "token",
    "api_key",
    "apikey",
    "authorization",
    "headers",
    "payload",
    "connection_id",
    "credentials",
    "access_key",
    "secret_key",
}


def database_identity(connection_identity: str, database: str) -> tuple[str, str]:
    qualified_name = f"{connection_identity}:{database}"
    return qualified_name, f"db:{connection_identity}:{database}"


def schema_identity(connection_identity: str, database: str, schema: str) -> tuple[str, str]:
    qualified_name = f"{database}.{schema}"
    return qualified_name, f"schema:{connection_identity}:{database}:{schema}"


def relation_identity(
    connection_identity: str, database: str, schema: str, name: str
) -> tuple[str, str]:
    qualified_name = f"{database}.{schema}.{name}"
    return qualified_name, f"rel:{connection_identity}:{database}:{schema}:{name}"


def extraction_source_identity(native_id: str) -> tuple[str, str]:
    return f"extraction:{native_id}", f"extraction:{native_id}"


def data_source_identity(native_id: str) -> tuple[str, str]:
    return f"datasource:{native_id}", f"datasource:{native_id}"


def url_data_source_identity(normalized_url: str) -> tuple[str, str]:
    qualified_name = f"datasource:url:{normalized_url}"
    return qualified_name, qualified_name


def process_identity(extraction_source_id: str, handler_key: str) -> tuple[str, str]:
    qualified_name = f"process:{extraction_source_id}:{handler_key}"
    return qualified_name, qualified_name


def airflow_process_identity(module_name: str) -> tuple[str, str]:
    qualified_name = f"process:airflow:{module_name}"
    return qualified_name, qualified_name


def airflow_extraction_identity(native_id: str) -> tuple[str, str]:
    return extraction_source_identity(f"airflow:{native_id}")


def storage_location_identity(normalized_path: str) -> tuple[str, str]:
    qualified_name = f"storage:{normalized_path}"
    return qualified_name, qualified_name


def unresolved_target_identity(database: str, schema: str, name: str) -> tuple[str, str]:
    qualified_name = f"unresolved:{database}.{schema}.{name}"
    return qualified_name, qualified_name


def display_object_name(database: str, schema: str, name: str) -> str:
    return f"{schema}.{name}" if database else name


def strip_secrets(payload: Any) -> Any:
    """Drop credentials and runtime secrets before Portal persistence."""
    if isinstance(payload, dict):
        cleaned: dict[str, Any] = {}
        for key, value in payload.items():
            if key.lower() in SECRET_ATTRIBUTE_KEYS:
                continue
            cleaned[key] = strip_secrets(value)
        return cleaned
    if isinstance(payload, list):
        return [strip_secrets(item) for item in payload]
    return payload


def compute_structure_hash(
    asset_type: AssetType,
    columns: Iterable[AssetColumn],
    constraints: list[dict[str, Any]] | None = None,
) -> str:
    payload = {
        "object_type": str(asset_type),
        "columns": [
            {
                "ordinal": column.ordinal,
                "name": column.name,
                "data_type": column.data_type,
                "nullable": column.nullable,
            }
            for column in sorted(columns, key=lambda item: item.ordinal)
        ],
        "constraints": constraints or [],
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def column_diff(previous: list[AssetColumn], current: list[AssetColumn]) -> dict[str, Any]:
    previous_by_name = {column.name: column for column in previous}
    current_by_name = {column.name: column for column in current}
    added = [
        {
            "name": column.name,
            "data_type": column.data_type,
            "nullable": column.nullable,
        }
        for name, column in current_by_name.items()
        if name not in previous_by_name
    ]
    removed = [name for name in previous_by_name if name not in current_by_name]
    changed = []
    for name, current_column in current_by_name.items():
        previous_column = previous_by_name.get(name)
        if previous_column is None:
            continue
        if (
            previous_column.data_type != current_column.data_type
            or previous_column.nullable != current_column.nullable
        ):
            changed.append(
                {
                    "name": name,
                    "from": {
                        "data_type": previous_column.data_type,
                        "nullable": previous_column.nullable,
                    },
                    "to": {
                        "data_type": current_column.data_type,
                        "nullable": current_column.nullable,
                    },
                }
            )
    return {"added": added, "removed": removed, "changed": changed}
