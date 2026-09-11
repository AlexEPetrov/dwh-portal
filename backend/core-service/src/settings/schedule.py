from pydantic_settings import BaseSettings, SettingsConfigDict


class ScheduleSettings(BaseSettings):
    """
    Параметры - расписания
    """

    model_config = SettingsConfigDict(
        env_prefix="APP_SCHEDULE_",  # Prefix for all environment variables
    )

    load_curves: str = None 
    load_objects: str = None 
    run_valuation: str = None
    run_simulation: str = None 