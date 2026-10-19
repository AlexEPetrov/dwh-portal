from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from domains.catalog.collectors.runner import run_daily_collection
from domains.catalog.models import CollectorStatus
from domains.catalog.repositories.ports import PortalStore
from settings.portal import DwhCollectorSettings, PortalSettings

AirflowLineageMode = Literal["catalog", "code"]


def normalize_schema_names(values: list[str] | None) -> tuple[str, ...] | None:
    """Return the schema allow-list for one collect run.

    ``None`` means every user schema. Names are trimmed, comma-separated
    entries are split, and duplicates are dropped while preserving order.
    An empty list is the same as omitting the filter.
    """
    if not values:
        return None
    ordered: list[str] = []
    seen: set[str] = set()
    for raw in values:
        for part in str(raw).split(","):
            name = part.strip()
            if not name or name in seen:
                continue
            seen.add(name)
            ordered.append(name)
    return tuple(ordered) or None


@dataclass(frozen=True)
class CollectOptions:
    """Operator flags for a portal collect run."""

    reset: bool = False
    airflow_lineage_mode: AirflowLineageMode | None = None
    schemas: tuple[str, ...] | None = None


@dataclass
class CollectRunSummary:
    status: str
    message: str | None = None
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class CollectResult:
    """Operator-facing summary of one collect run."""

    reset: bool
    airflow_lineage_mode: str
    failed: bool
    runs: dict[str, CollectRunSummary]
    schemas: list[str] | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "reset": self.reset,
            "airflow_lineage_mode": self.airflow_lineage_mode,
            "schemas": self.schemas,
            "failed": self.failed,
            "runs": {
                name: {
                    "status": item.status,
                    "message": item.message,
                    "details": item.details,
                }
                for name, item in self.runs.items()
            },
        }


class CollectionService:
    """Run snapshot collectors with operator flags (CLI or HTTP)."""

    def __init__(self, store: PortalStore, portal_settings: PortalSettings | None = None):
        self._store = store
        self._portal = portal_settings or PortalSettings()

    def run(self, options: CollectOptions | None = None) -> CollectResult:
        """Execute the daily collection sequence and return a completeness summary."""
        options = options or CollectOptions()
        reset = bool(options.reset or self._portal.reset_on_collect)
        schemas = normalize_schema_names(list(options.schemas) if options.schemas else None)
        dwh_settings = DwhCollectorSettings()
        mode = options.airflow_lineage_mode or dwh_settings.airflow_lineage_mode
        if options.airflow_lineage_mode is not None:
            dwh_settings = dwh_settings.model_copy(
                update={"airflow_lineage_mode": options.airflow_lineage_mode}
            )
        if reset:
            self._store.purge()
        raw = run_daily_collection(self._store, settings=dwh_settings, schemas=schemas)
        runs = {
            name: CollectRunSummary(
                status=_status_value(run.status),
                message=run.message,
                details=dict(run.details or {}),
            )
            for name, run in raw.items()
        }
        failed = any(item.status == CollectorStatus.FAILED.value for item in runs.values())
        return CollectResult(
            reset=reset,
            airflow_lineage_mode=mode,
            failed=failed,
            runs=runs,
            schemas=list(schemas) if schemas else None,
        )


def _status_value(status: Any) -> str:
    if hasattr(status, "value"):
        return str(status.value)
    return str(status)
