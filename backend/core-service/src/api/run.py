import logging
import os

import urllib3
import uvicorn
from uvicorn.config import LOGGING_CONFIG

from api.host import app
from domains.management.bootstrap import register as register_domain_management
from domains.management.repositories import register_repositories
from shared.logging.configuration import LogConfig
from shared.nullables import require

if __name__ == "__main__":

    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    logging.getLogger().info("Инициализируем инфраструктуру")

    LogConfig.load(LOGGING_CONFIG)

    logging.getLogger().info("Регистрируем зависимости")

    register_repositories()
    register_domain_management()

    logging.getLogger().info("Регистрируем фоновые сервисы")

    logging.getLogger().info("Запускаем API")

    port = os.getenv("APP_API_PORT")

    # пока отлаживаемся, через uvicorn.run
    uvicorn.run(
        app, host="0.0.0.0", port=int(require(port, msg="APP_API_PORT should be specified"))
    )
