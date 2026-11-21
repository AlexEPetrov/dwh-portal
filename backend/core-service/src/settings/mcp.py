"""Operator-controlled access to Portal's read-only MCP interface."""

from urllib.parse import urlsplit

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class CatalogMcpSettings(BaseSettings):
    """Keep MCP enablement, temporary anonymous reads and credentials independent."""

    model_config = SettingsConfigDict(env_prefix="APP_MCP_")

    enabled: bool = False
    allow_anonymous_read: bool = False
    token: SecretStr = SecretStr("")
    allowed_hosts: list[str] = Field(
        default_factory=lambda: ["localhost:*", "127.0.0.1:*", "[::1]:*"]
    )
    allowed_origins: list[str] = Field(default_factory=list)
    public_base_url: str = ""

    @field_validator("public_base_url")
    @classmethod
    def validate_public_base_url(cls, value: str) -> str:
        """Never derive public navigation links from request headers or credentials."""
        if not value:
            return value
        parsed = urlsplit(value)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
            or parsed.path not in {"", "/"}
        ):
            raise ValueError("MCP public base URL must be an HTTP(S) origin without credentials")
        return value.rstrip("/")
