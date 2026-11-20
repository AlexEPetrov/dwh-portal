"""Startup-only memory exemption must not weaken SQL or explicit DB checks."""

import asyncio
import importlib
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from infrastructure.db import migration_check


@pytest.fixture(autouse=True)
def isolated_settings(monkeypatch):
    monkeypatch.setenv("APP_PORTAL_STORE", "memory")
    for key in ("HOST", "USER", "PASS", "DB"):
        monkeypatch.delenv(f"APP_DB_PSG_{key}", raising=False)


def status(ok):
    return migration_check.PortalMigrationStatus(
        ok=ok,
        heads=("expected-head",),
        current=("expected-head",) if ok else ("old-revision",),
        database="test-portal",
        detail="current" if ok else "revision mismatch",
    )


def test_memory_startup_does_not_construct_db_settings_or_engine(monkeypatch):
    settings = Mock(side_effect=AssertionError("DB settings must not be constructed"))
    engine = Mock(side_effect=AssertionError("No DB connection is allowed"))
    monkeypatch.setattr(migration_check, "DbConnectionSettings", settings)
    monkeypatch.setattr(migration_check, "create_engine", engine)

    migration_check.ensure_portal_startup_migrations_current()

    settings.assert_not_called()
    engine.assert_not_called()


def test_sql_startup_checks_revisions(monkeypatch):
    monkeypatch.setenv("APP_PORTAL_STORE", "sql")
    inspect = Mock(return_value=status(True))
    monkeypatch.setattr(migration_check, "inspect_portal_migrations", inspect)

    migration_check.ensure_portal_startup_migrations_current()

    inspect.assert_called_once_with()


def test_sql_startup_rejects_old_revisions(monkeypatch):
    monkeypatch.setenv("APP_PORTAL_STORE", "sql")
    monkeypatch.setattr(
        migration_check, "inspect_portal_migrations", Mock(return_value=status(False))
    )

    with pytest.raises(SystemExit) as error:
        migration_check.ensure_portal_startup_migrations_current()

    assert error.value.code == 1


def test_sql_startup_rejects_missing_db_settings():
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv("APP_PORTAL_STORE", "sql")
        with pytest.raises(SystemExit) as error:
            migration_check.ensure_portal_startup_migrations_current()
    assert error.value.code == 1
    assert isinstance(error.value.__cause__, ValidationError)


def test_sql_startup_rejects_inspection_errors(monkeypatch):
    monkeypatch.setenv("APP_PORTAL_STORE", "sql")
    monkeypatch.setattr(
        migration_check, "inspect_portal_migrations", Mock(side_effect=RuntimeError("unavailable"))
    )

    with pytest.raises(SystemExit) as error:
        migration_check.ensure_portal_startup_migrations_current()

    assert error.value.code == 1


def test_invalid_store_does_not_silently_skip_migrations():
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv("APP_PORTAL_STORE", "unsupported")
        with pytest.raises(ValidationError):
            migration_check.ensure_portal_startup_migrations_current()


def test_explicit_db_check_stays_strict_with_memory_store():
    with pytest.raises(SystemExit) as error:
        migration_check.ensure_portal_migrations_current()
    assert error.value.code == 1
    assert isinstance(error.value.__cause__, ValidationError)


@pytest.mark.parametrize("ok, exit_code", [(True, 0), (False, 1)])
def test_cli_checks_revisions_even_with_memory_store(monkeypatch, ok, exit_code):
    inspect = Mock(return_value=status(ok))
    monkeypatch.setattr(migration_check, "inspect_portal_migrations", inspect)

    assert migration_check.main([]) == exit_code
    inspect.assert_called_once_with()


def test_cli_rejects_missing_db_settings_even_with_memory_store():
    assert migration_check.main([]) == 1


@pytest.mark.parametrize("module_name", ["api.host", "api.portal_host"])
def test_memory_host_starts_and_serves_http_without_postgres(monkeypatch, module_name):
    module = importlib.import_module(module_name)
    settings = Mock(side_effect=AssertionError("Startup must not require a DB"))
    monkeypatch.setattr(migration_check, "DbConnectionSettings", settings)

    with TestClient(module.app) as client:
        assert client.get("/openapi.json").status_code == 200
        if module_name == "api.host":
            response = client.get("/health")
            assert response.status_code == 200
            assert response.json()["checks"]["database"]["status"] == "skipped"

    settings.assert_not_called()


@pytest.mark.parametrize("module_name", ["api.host", "api.portal_host"])
def test_sql_host_refuses_startup_on_revision_mismatch(monkeypatch, module_name):
    module = importlib.import_module(module_name)
    monkeypatch.setenv("APP_PORTAL_STORE", "sql")
    inspect = Mock(return_value=status(False))
    monkeypatch.setattr(migration_check, "inspect_portal_migrations", inspect)

    async def startup():
        async with module.lifespan(module.app):
            pytest.fail("SQL host must not accept requests before migrations are current")

    with pytest.raises(SystemExit) as error:
        asyncio.run(startup())

    assert error.value.code == 1
    inspect.assert_called_once_with()
