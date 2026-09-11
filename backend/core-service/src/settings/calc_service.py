from pydantic_settings import BaseSettings, SettingsConfigDict


class CalcServiceSettings(BaseSettings):
    """
    Параметры доступа к сервису вычислений
    """

    model_config = SettingsConfigDict(
        env_prefix="APP_CALC_SERVICE_",  # Prefix for all environment variables
    )    

    host: str = None
    http_port: int = 0
    grpc_sock: str = None
    api_key: str = None 
