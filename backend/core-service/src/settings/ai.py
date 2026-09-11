from pydantic_settings import BaseSettings, SettingsConfigDict


class AiSettings(BaseSettings):
    """Настройки интеграции с локальным AI provider (Ollama)."""

    model_config = SettingsConfigDict(
        env_prefix="APP_AI_",
    )

    enabled: bool = False
    provider: str = "ollama"
    base_url: str = "http://ollama:11434"
    api_key: str | None = None
    model: str = "llama3.1:8b"
    timeout_sec: int = 600
