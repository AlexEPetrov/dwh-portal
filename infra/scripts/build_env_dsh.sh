#!/bin/bash
set -euo pipefail
DIRECTORY=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
export CI_ENVIRONMENT=dsh
exec bash "$DIRECTORY/_build_target.sh" "$@"
