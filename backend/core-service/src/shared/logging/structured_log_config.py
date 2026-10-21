import datetime
import json
import logging
import logging.config
import os
from typing import Dict, Optional

from shared.request_context import get_correlation_id, get_request_id

# ограничиваем объем информации, записываемой в лог
_skip_fields = {
    "name",
    "msg",
    "args",
    "levelname",
    "levelno",
    "pathname",
    "filename",
    "module",
    "exc_info",
    "exc_text",
    "stack_info",
    "lineno",
    "funcName",
    "created",
    "msecs",
    "relativeCreated",
    "thread",
    "threadName",
    "processName",
    "process",
    "taskName",
}


class PlainTextConsoleFormatter(logging.Formatter):
    """Human-friendly plain text output for console"""

    def format(self, record):
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        base_msg = f"{timestamp} [{record.levelname}] {record.name}: {record.getMessage()}"

        extra_fields = {
            k: v
            for k, v in record.__dict__.items()
            if k not in _skip_fields and not k.startswith("_")
        }

        # Add extra fields if they exist
        if extra_fields:
            extra_fields = " ".join(f"{k}={v}" for k, v in extra_fields.items())
            return f"{base_msg} | {extra_fields}"
        return base_msg


class FileJSONFormatter(logging.Formatter):
    """Compact JSON output for files"""

    def format(self, record):

        request_id = get_request_id()
        correlation_id = get_correlation_id()

        log_record = {
            "t": datetime.datetime.now().isoformat(),
            "logger": record.name,
            "level": record.levelname,
            "message": record.getMessage(),
            "correlation_id": correlation_id,
            "request_id": request_id,
        }
        # Add extra fields
        extra_fields = {
            k: v
            for k, v in record.__dict__.items()
            if k not in _skip_fields and not k.startswith("_")
        }
        log_record.update(extra_fields)

        return json.dumps(log_record, ensure_ascii=False)


def rotating_file_namer(default_name):
    base_filename, ext, num = default_name.split(".")
    date = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M")
    return f"{base_filename}.{date}.{num}.{ext}"


class StructLogConfiguration:

    @classmethod
    def create_logger(cls, logger_name, base_logger_name=None) -> logging.Logger:
        """Инициализация логгера. ВНИМАНИЕ: здесь осознанно выбран уход от стандартного иерархического использования (copying + propate=False)
        ввиду пойманных как-то багов в виде неотрабатывания всех хендлеров. Возиться с этим нет желания, поэтому добавляем прозрачности
        коду в виде явной инициализации дочерних логгеров"""
        logger = logging.getLogger(
            (base_logger_name + "." if base_logger_name else "") + logger_name
        )

        # Ensure we don't reattach handlers repeatedly
        if not logger.handlers:
            base_logger = logging.getLogger(base_logger_name)

            # Inherit handlers from base logger
            for handler in base_logger.handlers:
                logger.addHandler(handler)

            logger.setLevel(base_logger.level)
            logger.propagate = False  # Prevent duplicate logs in root
        return logger

    @classmethod
    def load(cls, extra_logging_config: Optional[Dict] = None):
        """Загрузка конфигурации логгирования (Structured logging). 2 лога - для подсервисов management (по умолчанию) и valuation"""

        # если не под docker - logs folder как подпапка текущего каталога.
        # под docker - /app/logs/*
        logs_dir = "logs"
        if StructLogConfiguration._is_under_docker():
            logs_dir = "/app/logs"
        os.makedirs(logs_dir, exist_ok=True)
        management_service_log_path = os.path.join(logs_dir, "portal-management-service.json")
        valuation_service_log_path = os.path.join(logs_dir, "portal-valuation-service.json")
        # Configure logging
        logging.config.dictConfig(
            {
                "version": 1,
                "formatters": {
                    "plain_text": {"()": PlainTextConsoleFormatter},
                    "file_json": {"()": FileJSONFormatter},
                },
                "handlers": {
                    "console": {
                        "class": "logging.StreamHandler",
                        "formatter": "plain_text",
                        "stream": "ext://sys.stdout",
                    },
                    "management": {
                        "class": "logging.handlers.RotatingFileHandler",
                        "filename": management_service_log_path,
                        "formatter": "file_json",
                        "encoding": "utf-8",
                        "maxBytes": (8 * 1024 * 1024 * 5),
                        "backupCount": 20,
                    },
                    "valuation": {
                        "class": "logging.handlers.RotatingFileHandler",
                        "filename": valuation_service_log_path,
                        "formatter": "file_json",
                        "encoding": "utf-8",
                        "maxBytes": (8 * 1024 * 1024 * 5),
                        "backupCount": 20,
                    },
                },
                "loggers": {
                    "management": {
                        "handlers": ["console", "management"],
                        "level": "INFO",
                        "propagate": False,
                    },
                    "valuation": {
                        "handlers": ["console", "valuation"],
                        "level": "INFO",
                        "propagate": False,
                    },
                },
                "root": {"level": "INFO", "handlers": ["console", "management"]},
            }
        )

        logging.getLogger().handlers[1].namer = rotating_file_namer

    @staticmethod
    def _is_under_docker():
        return os.path.exists("/.dockerenv")
