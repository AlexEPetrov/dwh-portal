"""
Проверка работоспособности. Используется в HC API и как проверка перед запуском тяжелых задач
TODO - timeouts, cache check state
"""

from typing import List, Tuple

from sqlalchemy import text

from infrastructure.db.session_management import SessionProvider
from infrastructure.files.filestore_registry import FileStoreRegistry
from settings.location import LocationsSettings


def check_database_availability() -> List[Tuple[str, str, str]]:
    try:
        with SessionProvider().create_session() as s:
            s.execute(text("SELECT 1"))
            return [("database", "healthy", "OK")]
    except Exception as ex:
        return [("database", "unhealthy", str(ex))]


def check_folder_availability() -> List[Tuple[str, str, str]]:
    return [(name, "healthy", "OK")]


def check_calculation_engine() -> List[Tuple[str, str, str]]:
    return [("calc_engine", "healthy", "OK")]


def check_all() -> Tuple[bool, dict]:
    check_results = (
        check_database_availability() + check_folder_availability() + check_calculation_engine()
    )

    is_healthy = all(t[1].lower() == "healthy" for t in check_results)

    result = {
        "status": "healthy" if is_healthy else "unhealthy",
        "service": "gtrm-core-service",
        "checks": {
            name: {"status": status, "message": message} for name, status, message in check_results
        },
    }

    return is_healthy, result
