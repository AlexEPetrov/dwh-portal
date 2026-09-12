"""CLI: run portal collectors into the configured PortalStore.

Usage (from backend/core-service with PYTHONPATH=.):

    APP_PORTAL_STORE=sql python -m domains.catalog.collect

Wipe previous portal snapshots, then collect:

    APP_PORTAL_STORE=sql python -m domains.catalog.collect --reset

Airflow lineage matching:

    python -m domains.catalog.collect --airflow-lineage-mode catalog
    python -m domains.catalog.collect --airflow-lineage-mode code

Optional DWH connection for live collectors:

    APP_DWH_PSG_HOST=... APP_DWH_PSG_DB=... APP_DWH_PSG_USER=... APP_DWH_PSG_PASS=...
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Literal

from domains.catalog.runtime import create_portal_store, get_portal_settings
from domains.catalog.services.collection_service import CollectionService, CollectOptions


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run DWH Portal collectors")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Purge sol_dwh_portal snapshots before collecting (APP_PORTAL_RESET_ON_COLLECT)",
    )
    parser.add_argument(
        "--airflow-lineage-mode",
        choices=("catalog", "code"),
        default=None,
        help="Airflow WRITES_TO matching: catalog (snapshot tables) or code (DAG AST)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    settings = get_portal_settings()
    store = create_portal_store(settings)
    mode: Literal["catalog", "code"] | None = args.airflow_lineage_mode
    reset = args.reset or settings.reset_on_collect
    print(
        f"portal store={settings.store} seed_demo={settings.seed_demo and settings.store == 'memory'} "
        f"reset={reset} airflow_lineage_mode={mode or 'env'}",
        file=sys.stderr,
    )
    result = CollectionService(store, settings).run(
        CollectOptions(reset=args.reset, airflow_lineage_mode=mode)
    )
    if result.reset:
        print("purged previous portal snapshots", file=sys.stderr)
    print(json.dumps(result.as_dict(), indent=2, default=str))
    return 1 if result.failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
