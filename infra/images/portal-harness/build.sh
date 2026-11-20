#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../../.." && pwd)
cd "$ROOT"

# Distinct from the existing Portal tag; no existing deployment is restarted.
docker build --platform linux/amd64 --progress plain \
    --file infra/images/portal-harness/Dockerfile \
    --tag 134/dwh-portal-dsh:0.2.2-rc.5-source-experimental .
