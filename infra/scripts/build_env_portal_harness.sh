#!/bin/bash
set -euo pipefail
DIRECTORY=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
export CI_ENVIRONMENT=portal-harness
exec bash "$DIRECTORY/_build_target.sh" "$@"
