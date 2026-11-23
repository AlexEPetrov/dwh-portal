#!/bin/bash
set -euo pipefail

DIRECTORY=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
ACTION=${1:-}
if [[ "$ACTION" != up && "$ACTION" != down ]]; then
    printf 'Usage: compose.sh up|down [environment-file]\n' >&2
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
ENV_FILE="$ENV_DIRECTORY/$(basename -- "$ENV_FILE")"
COMPOSE_FILE="$DIRECTORY/docker-compose-dsh.yml"
if [[ ! -f "$COMPOSE_FILE" ]]; then
    COMPOSE_FILE="$DIRECTORY/../../compose/docker-compose-dsh.yml"
fi
if [[ ! -f "$COMPOSE_FILE" ]]; then
    printf 'DSH Compose definition is missing\n' >&2
    exit 2
fi

ARGS=(compose --project-name dwh-dsh --env-file "$ENV_FILE" --file "$COMPOSE_FILE")
if [[ "$ACTION" == up ]]; then
    exec docker "${ARGS[@]}" up -d
fi
# Preserve this project's named state; never affect the Portal project.
exec docker "${ARGS[@]}" down
