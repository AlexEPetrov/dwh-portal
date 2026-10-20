"""Log helpers for configured DWH / Portal database names."""

from __future__ import annotations

import logging
import os

from settings.database import DbConnectionSettings
from settings.portal import DwhCollectorSettings


def format_database_targets(
    dwh_settings: DwhCollectorSettings | None = None,
    portal_db_settings: DbConnectionSettings | None = None,
) -> str:
    """Human-readable DWH and Portal database names from env settings."""
    if dwh_settings is not None:
        dwh_name = dwh_settings.psg_db or "(not configured)"
    else:
        dwh_name = os.getenv("APP_DWH_PSG_DB") or "(not configured)"

    if portal_db_settings is not None:
        portal_name = portal_db_settings.psg_db or "(not configured)"
    else:
        portal_name = os.getenv("APP_DB_PSG_DB") or "(not configured)"

    return f"DWH database={dwh_name}; Portal database={portal_name}"


def log_database_targets(
    logger: logging.Logger | None = None,
    *,
    dwh_settings: DwhCollectorSettings | None = None,
    portal_db_settings: DbConnectionSettings | None = None,
) -> str:
    """Log configured DWH/Portal database names; return the same message."""
    message = format_database_targets(dwh_settings, portal_db_settings)
    (logger or logging.getLogger(__name__)).info(message)
    return message
