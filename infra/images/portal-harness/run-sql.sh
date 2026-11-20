#!/bin/bash
set -euo pipefail

if [[ $# -ne 1 || ! -f "$1" ]]; then
    printf 'Usage: bash infra/images/portal-harness/run-sql.sh <existing-Portal-env-file>\n' >&2
    exit 2
fi

DIRECTORY=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
ENV_DIRECTORY=$(CDPATH= cd -- "$(dirname -- "$1")" && pwd)
export PORTAL_ENV_FILE="$ENV_DIRECTORY/$(basename -- "$1")"

# Compose parses the existing file; never source shell code or print credentials.
# A distinct project/service leaves the existing core-service deployment alone.
# Startup validates existing migrations but does not apply or collect anything.
exec docker compose --project-name dwh-portal-harness \
    --env-file "$PORTAL_ENV_FILE" \
    --file "$DIRECTORY/compose-sql.json" up -d
