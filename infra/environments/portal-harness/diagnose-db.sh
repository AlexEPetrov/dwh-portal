#!/bin/bash
set -euo pipefail
DIRECTORY=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
exec bash "$DIRECTORY/compose.sh" diagnose-db "$@"
