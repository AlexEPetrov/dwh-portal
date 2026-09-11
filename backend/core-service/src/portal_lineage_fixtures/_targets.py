"""Shared helpers for fake loader metadata contracts."""

from __future__ import annotations


def table(schema: str, name: str, *, database: str = "dwh") -> dict:
    return {"type": "table", "database": database, "schema": schema, "name": name}


def storage(path: str, *, kind: str = "s3") -> dict:
    """PROCESS WRITES_TO file/object store (S3, local file path, etc.)."""
    return {"type": kind, "path": path}


def view_of(
    schema: str,
    view_name: str,
    base_table: str,
    *,
    database: str = "dwh",
    base_schema: str | None = None,
) -> dict:
    """View derived from a table (VIEW DERIVED_FROM TABLE — not WRITES_TO)."""
    return {
        "type": "view",
        "database": database,
        "schema": schema,
        "name": view_name,
        "derived_from": table(base_schema or schema, base_table, database=database),
    }
