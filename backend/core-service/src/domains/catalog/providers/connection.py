"""Shared DWH connection helpers for catalog collectors."""

from __future__ import annotations

from typing import Any

from settings.portal import DwhCollectorSettings

# Session-level guard: writes fail even if the DB role allows them.
# Not a substitute for a least-privilege role, but required when one is unavailable.
_READ_ONLY_OPTIONS = "-c default_transaction_read_only=on"


def connect_dwh_readonly(settings: DwhCollectorSettings) -> Any:
    """Open a PostgreSQL connection to DWH with default_transaction_read_only=on."""
    import psycopg2

    if not settings.psg_host or not settings.psg_db:
        raise RuntimeError("DWH collector connection is not configured")
    return psycopg2.connect(
        host=settings.psg_host,
        port=settings.psg_port,
        user=settings.psg_user,
        password=settings.psg_pass,
        dbname=settings.psg_db,
        options=_READ_ONLY_OPTIONS,
    )
