"""Shared helpers for fake loader metadata contracts."""

from __future__ import annotations


def table(schema: str, name: str, *, database: str = "dwh") -> dict:
    return {"type": "table", "database": database, "schema": schema, "name": name}


def view(schema: str, name: str, *, database: str = "dwh") -> dict:
    return {"type": "view", "database": database, "schema": schema, "name": name}
