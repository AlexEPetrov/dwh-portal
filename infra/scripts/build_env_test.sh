#!/bin/bash
set -euo pipefail
# Thin local/CI compatibility entry point into the shared release engine.
DIRECTORY=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
export CI_ENVIRONMENT=test
exec bash "$DIRECTORY/_build_target.sh" "$@"
