from pydantic_settings import BaseSettings, SettingsConfigDict


class LocationsSettings(BaseSettings):
    """
    Параметры-имена папок для доступа к исходным файлам симуляций и результатам расчета.
    """

    model_config = SettingsConfigDict(
        env_prefix="APP_LOC_",  # Prefix for all environment variables
    )

    load_files_path: str | None = None
    archive_path: str | None = None
    temp_path: str | None = None
    repository_path: str | None = None
    documents: str | None = None
    """Path to documents directory containing Excel source files for balance calculations."""

    simulation_source_root: str | None = None
    """# s:/backet_name/subpath1   OR /apps/subpath1"""
    simulation_source_path: str | None = None

    execution_presets_path: str | None = None
    """Path to directory containing simulation preset JSON files.
    Each file represents one preset. Placeholders like {operation_id} are supported."""

    filter_presets_path: str | None = None
    """Path to the read-only JSON collection used by valuation analysis filter controls."""

    enable_hive_parquet: bool = True
    """Флаг включения/выключения Hive-partitioned Parquet вывода"""

    # Новые поля для unified структуры (Этап 1)
    storage_root: str | None = None
    """Единый корень для всех результатов (executions, simulations, valuations).
    Пример: '/app_data' или 's3://bucket/app_data'"""

    executions_path: str = "executions/data"
    """Относительный путь для executions data внутри storage_root.
    По умолчанию: 'executions/data'"""
