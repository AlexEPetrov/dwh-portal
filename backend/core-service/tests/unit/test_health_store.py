"""Health reflects configured dependencies while SQL checks remain strict."""

from unittest.mock import MagicMock, Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from api.health import health_router
from infrastructure.services import health


def test_memory_health_skips_database_without_creating_session(monkeypatch):
    monkeypatch.setenv("APP_PORTAL_STORE", "memory")
    create_session = Mock(side_effect=AssertionError("No PostgreSQL in memory mode"))
    monkeypatch.setattr(health.SessionProvider, "create_session", create_session)

    healthy, payload = health.check_all()

    assert healthy is True
    assert payload["status"] == "healthy"
    assert payload["checks"]["database"]["status"] == "skipped"
    assert "in-memory" in payload["checks"]["database"]["message"]
    create_session.assert_not_called()


@pytest.mark.parametrize("available, expected_http", [(True, 200), (False, 503)])
def test_sql_health_still_probes_database(monkeypatch, available, expected_http):
    monkeypatch.setenv("APP_PORTAL_STORE", "sql")
    session = MagicMock()
    create_session = MagicMock()
    if available:
        create_session.return_value.__enter__.return_value = session
    else:
        create_session.side_effect = RuntimeError("database unavailable")
    monkeypatch.setattr(health.SessionProvider, "create_session", create_session)
    app = FastAPI()
    app.include_router(health_router)

    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == expected_http
    expected_status = "healthy" if available else "unhealthy"
    assert response.json()["status"] == expected_status
    assert response.json()["checks"]["database"]["status"] == expected_status
    create_session.assert_called_once_with()
    if available:
        session.execute.assert_called_once()
        assert str(session.execute.call_args.args[0]) == "SELECT 1"


def test_direct_database_probe_is_not_disabled_by_memory_setting(monkeypatch):
    monkeypatch.setenv("APP_PORTAL_STORE", "memory")
    create_session = Mock(side_effect=RuntimeError("database unavailable"))
    monkeypatch.setattr(health.SessionProvider, "create_session", create_session)

    assert health.check_database_availability() == [
        ("database", "unhealthy", "database unavailable")
    ]
    create_session.assert_called_once_with()


def test_invalid_store_does_not_report_healthy(monkeypatch):
    monkeypatch.setenv("APP_PORTAL_STORE", "invalid")
    with pytest.raises(ValidationError):
        health.check_all()
