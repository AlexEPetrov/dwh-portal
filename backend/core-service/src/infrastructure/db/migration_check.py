"""Startup check: Portal DB must be at Alembic head."""

from __future__ import annotations

import logging
import sys
from dataclasses import dataclass
from pathlib import Path

from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, text

from settings.database import DbConnectionSettings
from settings.portal import PortalSettings

logger = logging.getLogger(__name__)

PORTAL_VERSION_SCHEMA = "sol_dwh_portal"


@dataclass(frozen=True)
class PortalMigrationStatus:
    """Result of comparing Alembic heads with Portal DB revisions."""

    ok: bool
    heads: tuple[str, ...]
    current: tuple[str, ...]
    database: str
    detail: str


def _src_root() -> Path:
    # infrastructure/db/migration_check.py -> src/
    return Path(__file__).resolve().parents[2]


def _alembic_ini_path() -> Path:
    return _src_root() / "alembic.ini"


def _alembic_script_path() -> Path:
    return _src_root() / "alembic"


def _portal_db_url(settings: DbConnectionSettings) -> str:
    return (
        f"postgresql+psycopg2://{settings.psg_user}:{settings.psg_pass}"
        f"@{settings.psg_host}:{settings.psg_port}/{settings.psg_db}"
    )


def inspect_portal_migrations(
    settings: DbConnectionSettings | None = None,
) -> PortalMigrationStatus:
    """Compare Alembic script heads with revisions applied in Portal DB."""
    settings = settings or DbConnectionSettings()
    ini_path = _alembic_ini_path()
    script_path = _alembic_script_path()
    if not ini_path.is_file():
        return PortalMigrationStatus(
            ok=False,
            heads=(),
            current=(),
            database=settings.psg_db or "(unknown)",
            detail=f"alembic.ini not found at {ini_path}",
        )
    if not script_path.is_dir():
        return PortalMigrationStatus(
            ok=False,
            heads=(),
            current=(),
            database=settings.psg_db or "(unknown)",
            detail=f"alembic scripts not found at {script_path}",
        )

    cfg = Config(str(ini_path))
    # ini has script_location=alembic (cwd-relative); pin absolute path under src/.
    cfg.set_main_option("script_location", str(script_path))
    cfg.set_main_option("sqlalchemy.url", _portal_db_url(settings))
    script = ScriptDirectory.from_config(cfg)
    heads = tuple(sorted(script.get_heads()))

    engine = create_engine(_portal_db_url(settings), pool_pre_ping=True)
    try:
        with engine.connect() as connection:
            schema_exists = connection.execute(
                text("SELECT 1 FROM information_schema.schemata " "WHERE schema_name = :schema"),
                {"schema": PORTAL_VERSION_SCHEMA},
            ).scalar()
            if not schema_exists:
                return PortalMigrationStatus(
                    ok=False,
                    heads=heads,
                    current=(),
                    database=settings.psg_db or "(unknown)",
                    detail=(
                        f"schema {PORTAL_VERSION_SCHEMA} is missing; " "run alembic upgrade head"
                    ),
                )

            context = MigrationContext.configure(
                connection,
                opts={"version_table_schema": PORTAL_VERSION_SCHEMA},
            )
            current = tuple(sorted(context.get_current_heads()))
    finally:
        engine.dispose()

    ok = bool(heads) and set(current) == set(heads)
    if ok:
        detail = f"Portal migrations are current ({', '.join(current)})"
    elif not current:
        detail = (
            f"no applied revisions in {PORTAL_VERSION_SCHEMA}; "
            f"expected head(s): {', '.join(heads) or '(none)'}"
        )
    else:
        detail = f"applied={', '.join(current)}; " f"expected head(s)={', '.join(heads)}"
    return PortalMigrationStatus(
        ok=ok,
        heads=heads,
        current=current,
        database=settings.psg_db or "(unknown)",
        detail=detail,
    )


def ensure_portal_startup_migrations_current() -> None:
    """Require SQL migrations at startup only when the configured store uses SQL.

    Validate the store selection before inspecting DB settings so the supported
    in-memory mode can start without PostgreSQL. Keep the explicit DB check and
    CLI independent of this startup-only exception.
    """
    if PortalSettings().store == "memory":
        logger.info("Portal store=memory; SQL migration check is not applicable")
        return
    ensure_portal_migrations_current()


def ensure_portal_migrations_current() -> None:
    """Exit the process if Portal DB is not at Alembic head."""
    try:
        status = inspect_portal_migrations()
    except Exception as exc:  # noqa: BLE001 - startup must not continue on check failure
        logger.error(
            "Portal migration check failed for database=%s: %s. "
            "Ensure APP_DB_PSG_* is set and alembic upgrade head was applied.",
            _safe_db_name(),
            exc,
        )
        raise SystemExit(1) from exc

    if status.ok:
        logger.info(
            "Portal database=%s migrations OK: %s",
            status.database,
            status.detail,
        )
        return

    logger.error(
        "Portal database=%s migrations are not current: %s. Exiting.",
        status.database,
        status.detail,
    )
    raise SystemExit(1)


def _safe_db_name() -> str:
    try:
        return DbConnectionSettings().psg_db or "(unknown)"
    except Exception:  # noqa: BLE001
        return "(not configured)"


def main(argv: list[str] | None = None) -> int:
    """CLI helper: exit 0 when migrations are current, else 1."""
    del argv  # unused; kept for symmetry with other CLIs
    try:
        ensure_portal_migrations_current()
    except SystemExit as exc:
        return int(exc.code or 1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
