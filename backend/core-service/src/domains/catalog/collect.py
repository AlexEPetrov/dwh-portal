"""CLI: run portal collectors into the configured PortalStore.

Usage (from backend/core-service with PYTHONPATH=.):

    APP_PORTAL_STORE=sql python -m domains.catalog.collect

Wipe previous portal snapshots, then collect:

    APP_PORTAL_STORE=sql python -m domains.catalog.collect --reset

Optional DWH connection for live collectors:

    APP_DWH_PSG_HOST=... APP_DWH_PSG_DB=... APP_DWH_PSG_USER=... APP_DWH_PSG_PASS=...
"""

from __future__ import annotations

import argparse
import json
import sys

from domains.catalog.collectors.runner import run_daily_collection
from domains.catalog.runtime import create_portal_store, get_portal_settings


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run DWH Portal collectors")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Purge sol_dwh_portal snapshots before collecting (APP_PORTAL_RESET_ON_COLLECT)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    settings = get_portal_settings()
    store = create_portal_store(settings)
    reset = args.reset or settings.reset_on_collect
    print(
        f"portal store={settings.store} seed_demo={settings.seed_demo and settings.store == 'memory'} reset={reset}",
        file=sys.stderr,
    )
    if reset:
        store.purge()
        print("purged previous portal snapshots", file=sys.stderr)
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
