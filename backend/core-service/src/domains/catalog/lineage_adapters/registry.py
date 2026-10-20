from __future__ import annotations

import datetime
import importlib
from typing import Any

from domains.catalog.lineage_adapters.protocol import LineageAdapter
from domains.catalog.lineage_adapters.runs import record_adapter_run
from domains.catalog.models import CollectorStatus
from domains.catalog.repositories.ports import PortalStore
from settings.portal import DwhCollectorSettings

BUILTIN_ADAPTERS = {
    "postgres_sql": "domains.catalog.lineage_adapters.postgres_sql:PostgresSqlLineageAdapter",
    "extraction_registry": (
        "domains.catalog.lineage_adapters.extraction_registry:ExtractionRegistryLineageAdapter"
    ),
    "python_modules": (
        "domains.catalog.lineage_adapters.python_modules:PythonModulesLineageAdapter"
    ),
    "airflow_dags": "domains.catalog.lineage_adapters.airflow_dags:AirflowDagsLineageAdapter",
}


def default_adapter_specs(settings: DwhCollectorSettings) -> list[str]:
    """Built-in adapters when APP_DWH_LINEAGE_ADAPTERS is unset.

    ``python_modules`` and ``airflow_dags`` are always included; without their
    respective roots the adapters record a skipped run instead of being omitted.
    """
    return ["postgres_sql", "extraction_registry", "python_modules", "airflow_dags"]


def parse_adapter_specs(settings: DwhCollectorSettings) -> list[str]:
    raw = (settings.lineage_adapters or "").strip()
    if raw:
        return [part.strip() for part in raw.split(",") if part.strip()]
    return default_adapter_specs(settings)


def resolve_adapter_class(spec: str) -> type:
    """Resolve a built-in name or `module:Class` plugin path."""
    target = BUILTIN_ADAPTERS.get(spec, spec)
    if ":" not in target:
        raise ValueError(
            f"Unknown lineage adapter {spec!r}; use a built-in name or module:Class"
        )
    module_name, class_name = target.split(":", 1)
    module = importlib.import_module(module_name)
    return getattr(module, class_name)


def adapter_name_for_spec(spec: str) -> str:
    if spec in BUILTIN_ADAPTERS:
        return spec
    if ":" in spec:
        return spec.rsplit(":", 1)[-1]
    return spec


class FailedLoadAdapter:
    """Stand-in when a plugin spec cannot be imported or constructed."""

    def __init__(self, name: str, store: PortalStore, error: Exception):
        self.name = name
        self._store = store
        self._error = error

    def collect(self, now: datetime.datetime | None = None) -> Any:
        started = now or datetime.datetime.now(datetime.timezone.utc)
        return record_adapter_run(
            self._store,
            name=self.name,
            started=started,
            status=CollectorStatus.FAILED,
            message=str(self._error),
            details={"error": str(self._error), "code": "ADAPTER_LOAD_FAILED"},
        )


def load_lineage_adapters(
    store: PortalStore,
    settings: DwhCollectorSettings | None = None,
    *,
    lineage_provider: Any | None = None,
    metadata_provider: Any | None = None,
) -> list[LineageAdapter]:
    """Instantiate configured adapters; load failures become FailedLoadAdapter."""
    settings = settings or DwhCollectorSettings()
    adapters: list[LineageAdapter] = []
    kwargs = {
        "lineage_provider": lineage_provider,
        "metadata_provider": metadata_provider,
    }
    for spec in parse_adapter_specs(settings):
        name = adapter_name_for_spec(spec)
        try:
            cls = resolve_adapter_class(spec)
            adapters.append(cls(store, settings, **kwargs))
        except Exception as exc:
            adapters.append(FailedLoadAdapter(name, store, exc))
    return adapters
