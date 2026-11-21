#!/bin/sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../../.." && pwd)
cd "$ROOT"
docker build --platform linux/amd64 --progress plain \
    --file infra/images/portal/Dockerfile \
    --tag 134/dwh-portal-core-service:1.2 .
