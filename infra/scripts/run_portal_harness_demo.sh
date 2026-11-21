#!/bin/bash
set -euo pipefail

# The tokenized entry URL is printed by DSH. Treat logs as credentials.
# Loopback-only publication; no Portal DB credentials and no external mounts.
exec docker run --rm --init \
    --publish 127.0.0.1:5053:5051 \
    --publish 127.0.0.1:3080:3080 \
    --env APP_PORTAL_STORE=memory \
    --env APP_PORTAL_SEED_DEMO=true \
    --env DSH_PUBLIC_URL=http://127.0.0.1:3080/ \
    --mount type=volume,source=dwh-portal-dsh-demo,target=/var/lib/dsh \
    134/dwh-portal-dsh:0.2.2-rc.5-source-experimental
