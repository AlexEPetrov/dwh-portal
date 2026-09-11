"""Настройки формирования пользовательских отчётов."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ReportingSettings(BaseSettings):
    """Ограничения синхронного reporting interface layer."""

    model_config = SettingsConfigDict(env_prefix="APP_REPORTING_")

    simulation_xlsx_max_raw_rows: int = Field(default=2_000_000, ge=1)
