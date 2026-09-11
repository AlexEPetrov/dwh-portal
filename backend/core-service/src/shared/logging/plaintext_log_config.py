import logging
import os
from typing import Optional, Dict


class PlainTextLogConfiguration:
    log_level: str
    format_str: str
    default_format = '[%(asctime)s - %(levelname)s] %(name)s: %(message)s'
    default_api_format = '[%(asctime)s - %(levelname)s] %(name)s: %(client_addr)s - %(request_line)s %(status_code)s'

    @classmethod
    def load(cls, extra_logging_config: Optional[Dict] = None):

        PlainTextLogConfiguration.log_level = os.environ.get("LOGLEVEL", "INFO").upper()
        PlainTextLogConfiguration.format_str = os.environ.get("LOGFORMAT", PlainTextLogConfiguration.default_format)
        logging.getLogger().setLevel(PlainTextLogConfiguration.log_level)
        logging.basicConfig(format=PlainTextLogConfiguration.format_str, force=True)

        if extra_logging_config is not None:
            extra_logging_config["formatters"]["default"]["fmt"] = PlainTextLogConfiguration.format_str
            extra_logging_config["formatters"]["access"]["fmt"] = PlainTextLogConfiguration.default_api_format
            logging.config.dictConfig(extra_logging_config)

    @classmethod
    def add_rotating_file_logger(cls, log_file_path: str):
        handler = logging.handlers.RotatingFileHandler(
            log_file_path, maxBytes=(1048576*5), backupCount=10
        )
        formatter = logging.Formatter(PlainTextLogConfiguration.default_format)
        handler.setFormatter(formatter)
        logging.getLogger().addHandler(handler)



