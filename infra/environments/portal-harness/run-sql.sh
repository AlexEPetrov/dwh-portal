#!/bin/bash
set -euo pipefail

if [[ $# -ne 1 || ! -f "$1" ]]; then
    printf 'Usage: bash infra/environments/portal-harness/run-sql.sh <existing-Portal-env-file>\n' >&2
    exit 2
fi

DIRECTORY=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
ENV_DIRECTORY=$(CDPATH= cd -- "$(dirname -- "$1")" && pwd)
export PORTAL_ENV_FILE="$ENV_DIRECTORY/$(basename -- "$1")"

# Compatibility entry point; up.sh is portable between checkout and release.
exec bash "$DIRECTORY/up.sh" "$PORTAL_ENV_FILE"
