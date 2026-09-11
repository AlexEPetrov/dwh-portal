from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class PortalSettings(BaseSettings):
    """Runtime options for the DWH Portal snapshot store.

    Target production path: APP_PORTAL_STORE=sql (schema `portal` in app DB).
    `seed_demo` applies only to the in-memory store; SQL never auto-seeds.
    """

    model_config = SettingsConfigDict(env_prefix="APP_PORTAL_")

    store: Literal["memory", "sql"] = "memory"
    seed_demo: bool = True
    stale_after_hours: int = 36
    lineage_max_depth: int = 8
    default_page_size: int = 50
    max_page_size: int = 200


class DwhCollectorSettings(BaseSettings):
    """Read-only DWH connection used only by collectors."""

    model_config = SettingsConfigDict(env_prefix="APP_DWH_")

    psg_host: str | None = None
    psg_port: int = 5432
    psg_user: str | None = None
    psg_pass: str | None = None
    psg_db: str | None = None
    connection_identity: str = "dwh"
    rest_metadata_timeout_seconds: float = 3.0
    rest_metadata_retries: int = 1
