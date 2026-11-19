from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class PortalSettings(BaseSettings):
    """Runtime options for the DWH Portal snapshot store.

    Target production path: APP_PORTAL_STORE=sql (schema `sol_dwh_portal` in app DB).
    `seed_demo` applies only to the in-memory store; SQL never auto-seeds.
    """

    model_config = SettingsConfigDict(env_prefix="APP_PORTAL_")

    store: Literal["memory", "sql"] = "memory"
    seed_demo: bool = True
    reset_on_collect: bool = False
    stale_after_hours: int = 36
    lineage_max_depth: int = 8
    default_page_size: int = 50
    max_page_size: int = 200


class DwhCollectorSettings(BaseSettings):
    """Read-only DWH connection used by collectors and live extraction load logs."""

    model_config = SettingsConfigDict(env_prefix="APP_DWH_")

    psg_host: str | None = None
    psg_port: int = 5432
    psg_user: str | None = None
    psg_pass: str | None = None
    psg_db: str | None = None
    connection_identity: str = "dwh"
    rest_metadata_timeout_seconds: float = 3.0
    rest_metadata_retries: int = 1
    # Comma-separated built-in names and/or module:Class plugin paths.
    # Default (unset/empty): postgres_sql,extraction_registry,airflow_dags.
    lineage_adapters: str | None = None
    # Local Airflow DAG sources for reverse lineage; never executed.
    # Required for airflow_dags to produce lineage (otherwise the adapter skips).
    airflow_dags_root: str | None = None
    # catalog: WRITES_TO only tables already in the catalog snapshot.
    # code: materialize write targets from DAG AST even if absent from the snapshot.
    airflow_lineage_mode: Literal["catalog", "code"] = "catalog"
    # Local Python loader / package sources for registry PROCESS AST lineage.
    # Distinct from airflow_dags_root — never share the setting in code.
    # Required for python_modules to produce WRITES_TO (otherwise the adapter skips).
    # Semicolon-separated roots: trim whitespace, ignore empty entries, deduplicate
    # resolved paths; module collisions are diagnosed, never resolved by order.
    python_modules_root: str | None = None
    # catalog: WRITES_TO only tables already in the catalog snapshot.
    # code: materialize write targets from module AST even if absent from the snapshot.
    python_modules_lineage_mode: Literal["catalog", "code"] = "catalog"
