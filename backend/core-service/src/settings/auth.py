from pydantic_settings import BaseSettings, SettingsConfigDict


class AuthSettings(BaseSettings):
    """Настройки authentication/authorization слоя."""

    model_config = SettingsConfigDict(
        env_prefix="APP_AUTH_",
    )

    # Session cookie
    session_cookie_name: str = "app_session"
    session_ttl_seconds: int = 60 * 60 * 8
    session_secret_key: str = "dev-auth-secret-change-me"
    session_secure_cookie: bool = False
    session_samesite: str = "lax"

    # Temporary username/password for Phase 1 foundation
    local_username: str = "dev"
    local_password: str = "dev"
    viewer_username: str = "viewer"
    viewer_password: str = "viewer"

    # Service API keys (comma-separated env: "k1,k2,k3")
    service_api_keys: str = "0000,dev"
