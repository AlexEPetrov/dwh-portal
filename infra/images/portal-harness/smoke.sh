#!/bin/sh
set -eu

# No published ports, application credentials, external network or host mounts.
# Only this temporary container is removed; existing deployments are untouched.
docker run --rm --init --network none \
    --entrypoint python3 \
    134/dwh-portal-dsh:0.2.2-rc.5-source-experimental \
    /opt/portal-harness/container_smoke.py
