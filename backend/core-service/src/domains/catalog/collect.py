"""CLI: run portal collectors into the configured PortalStore.

Usage (from backend/core-service with PYTHONPATH=.):

    APP_PORTAL_STORE=sql python -m domains.catalog.collect

Optional DWH connection for live collectors:

    APP_DWH_PSG_HOST=... APP_DWH_PSG_DB=... APP_DWH_PSG_USER=... APP_DWH_PSG_PASS=...
"""

from __future__ import annotations

import json
import sys

from domains.catalog.collectors.runner import run_daily_collection
from domains.catalog.runtime import create_portal_store, get_portal_settings


def main() -> int:
    settings = get_portal_settings()
    store = create_portal_store(settings)
    print(
        f"portal store={settings.store} seed_demo={settings.seed_demo and settings.store == 'memory'}",
        file=sys.stderr,
    )
    result = run_daily_collection(store)
    summary = {
        name: {
            "status": run.status.value if hasattr(run.status, "value") else run.status,
            "message": run.message,
            "details": run.details,
        }
        for name, run in result.items()
    }
    print(json.dumps(summary, indent=2, default=str))
    failed = any(
        (run.status.value if hasattr(run.status, "value") else run.status) == "FAILED"
        for run in result.values()
    )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
