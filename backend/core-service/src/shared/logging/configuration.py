from shared.logging.structured_log_config import StructLogConfiguration


class LogConfig:
    """Application-level конфигурация логгирования"""

    @staticmethod
    def load(config):
        """Загрузка конфигурации логгирования"""
        StructLogConfiguration.load(config)

    @staticmethod
    def create_logger(name, base_name=None):
        """Создание логгера"""
        return StructLogConfiguration.create_logger(name, base_name)
