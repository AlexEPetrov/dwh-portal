"""Health checks for Portal API and its PostgreSQL store."""

from typing import List, Tuple

from sqlalchemy import text

from infrastructure.db.session_management import SessionProvider


def check_database_availability() -> List[Tuple[str, str, str]]:
    try:
        with SessionProvider.create_session() as session:
            session.execute(text("SELECT 1"))
            return [("database", "healthy", "OK")]
    except Exception as exc:
        return [("database", "unhealthy", str(exc))]


def check_all() -> Tuple[bool, dict]:
    check_results = check_database_availability()
    is_healthy = all(status.lower() == "healthy" for _, status, _ in check_results)
    return is_healthy, {
        "status": "healthy" if is_healthy else "unhealthy",
        "service": "dwh-portal-core-service",
        "checks": {
            name: {"status": status, "message": message}
            for name, status, message in check_results
        },
    }
