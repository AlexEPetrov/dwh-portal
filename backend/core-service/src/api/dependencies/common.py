import uuid

from fastapi import BackgroundTasks, HTTPException, status

from infrastructure.services.health import check_all
from shared.cqrs.core import CommandBus
from shared.cqrs.ports import JobScheduler
from shared.logging.configuration import LogConfig


def command_bus(logger_name: str, base_logger_name: str = "management"):
    return CommandBus(logger=LogConfig.create_logger(logger_name, base_logger_name))


def command_logger(logger_name: str, base_logger_name: str = "management"):
    return LogConfig.create_logger(logger_name, base_logger_name)


class FastApiBackgroundScheduler(JobScheduler):
    """Простой планировщик задач, который использует BackgroundTasks из FastAPI для выполнения задач в фоне."""

    def __init__(self, background_tasks: BackgroundTasks):
        self._bg = background_tasks

    def submit(self, fn, *, name: str | None = None) -> str:
        job_id = str(uuid.uuid4())
        self._bg.add_task(fn)
        return job_id


def health_check() -> bool:
    hc_status, details = check_all()
    if not hc_status:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=details,
        )
    return hc_status
