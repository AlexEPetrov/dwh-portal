#!/bin/bash
set -euo pipefail
# Compatibility profile router; no independent build or destructive cleanup.
DIRECTORY=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
exec python3 -B "$DIRECTORY/build_release.py" "${CI_ENVIRONMENT:?Set CI_ENVIRONMENT to test or portal-harness}" "$@"
