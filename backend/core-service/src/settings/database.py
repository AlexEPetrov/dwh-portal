from pydantic_settings import BaseSettings, SettingsConfigDict


class DbConnectionSettings(BaseSettings):
    """
    Параметры доступа к БД
    """

    model_config = SettingsConfigDict(
        env_prefix="APP_DB_",  # Prefix for all environment variables
    )    

    psg_host: str = None
    psg_port: int = 0
    psg_user: str = None
    psg_pass: str = None
    psg_db: str = None
    orm_debug_mode: bool = False
    orm_pre_ping: bool = False 
    orm_pool_recycle: int = 3600
