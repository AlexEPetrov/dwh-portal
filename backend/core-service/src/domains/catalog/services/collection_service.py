from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from domains.catalog.collectors.runner import run_daily_collection
from domains.catalog.models import CollectorStatus
from domains.catalog.repositories.ports import PortalStore
from settings.portal import DwhCollectorSettings, PortalSettings

AirflowLineageMode = Literal["catalog", "code"]


@dataclass(frozen=True)
class CollectOptions:
    """Operator flags for a portal collect run."""

    reset: bool = False
    airflow_lineage_mode: AirflowLineageMode | None = None


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

    def as_dict(self) -> dict[str, Any]:
        return {
            "reset": self.reset,
            "airflow_lineage_mode": self.airflow_lineage_mode,
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
        dwh_settings = DwhCollectorSettings()
        mode = options.airflow_lineage_mode or dwh_settings.airflow_lineage_mode
        if options.airflow_lineage_mode is not None:
            dwh_settings = dwh_settings.model_copy(
                update={"airflow_lineage_mode": options.airflow_lineage_mode}
            )
        if reset:
            self._store.purge()
        raw = run_daily_collection(self._store, settings=dwh_settings)
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
        )


def _status_value(status: Any) -> str:
    if hasattr(status, "value"):
        return str(status.value)
    return str(status)
