#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
if [[ -f .venv/bin/activate ]]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi
export APP_PORTAL_STORE=sql
export APP_PORTAL_SEED_DEMO=false
export APP_DWH_PSG_HOST="${APP_DWH_PSG_HOST:-localhost}"
export APP_DWH_PSG_PORT="${APP_DWH_PSG_PORT:-5432}"
export APP_DWH_PSG_DB="${APP_DWH_PSG_DB:-dwh}"
export APP_DWH_PSG_USER="${APP_DWH_PSG_USER:-postgres}"
export APP_DWH_PSG_PASS="${APP_DWH_PSG_PASS:-postgres}"
export APP_DB_PSG_HOST="${APP_DB_PSG_HOST:-localhost}"
export APP_DB_PSG_PORT="${APP_DB_PSG_PORT:-5432}"
export APP_DB_PSG_DB="${APP_DB_PSG_DB:-dwh}"
export APP_DB_PSG_USER="${APP_DB_PSG_USER:-postgres}"
export APP_DB_PSG_PASS="${APP_DB_PSG_PASS:-postgres}"
cd src && alembic upgrade head && cd ..
PYTHONPATH=./src python -m domains.catalog.collect
