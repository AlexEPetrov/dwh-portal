#!/bin/bash
set -euo pipefail

DIRECTORY=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
ACTION=${1:-}
if [[ "$ACTION" != up && "$ACTION" != down && "$ACTION" != diagnose-db ]]; then
    printf 'Usage: compose.sh up|down|diagnose-db [environment-file]\n' >&2
    exit 2
fi
shift
if [[ $# -gt 1 ]]; then
    printf 'Pass at most one environment file\n' >&2
    exit 2
fi
ENV_FILE=${1:-"$DIRECTORY/.env"}
if [[ ! -f "$ENV_FILE" ]]; then
    printf 'Environment file is missing; pass its path or provide .env beside the launchers\n' >&2
    exit 2
fi
ENV_DIRECTORY=$(CDPATH= cd -- "$(dirname -- "$ENV_FILE")" && pwd)
export PORTAL_ENV_FILE="$ENV_DIRECTORY/$(basename -- "$ENV_FILE")"

# A prepared release is self-contained. A checkout keeps composition canonical.
COMPOSE_FILE="$DIRECTORY/docker-compose-portal-harness.yml"
if [[ ! -f "$COMPOSE_FILE" ]]; then
    COMPOSE_FILE="$DIRECTORY/../../compose/docker-compose-portal-harness.yml"
fi
if [[ ! -f "$COMPOSE_FILE" ]]; then
    printf 'Portal harness Compose definition is missing\n' >&2
    exit 2
fi

ARGS=(compose --project-name dwh-portal-harness --env-file "$PORTAL_ENV_FILE" --file "$COMPOSE_FILE")
if [[ "$ACTION" == diagnose-db ]]; then
    # Same image, env, network and host alias; no service startup or port binding.
    # Older Compose supports service pull_policy but not `run --pull`.
    # Apply this policy only to diagnostics; normal up/down remain unchanged.
    exec docker "${ARGS[@]}" --file - run --rm --no-deps -T \
        --entrypoint python3 portal-harness /opt/portal/diagnose_db.py <<'DIAGNOSTIC_COMPOSE'
services:
  portal-harness:
    pull_policy: never
DIAGNOSTIC_COMPOSE
fi
if [[ "$ACTION" == up ]]; then
    exec docker "${ARGS[@]}" up -d
fi
# Intentionally no --volumes, --rmi or --remove-orphans: preserve owner state.
exec docker "${ARGS[@]}" down
