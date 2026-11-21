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
    printf 'Test environment file is missing\n' >&2
    exit 2
fi
ENV_DIRECTORY=$(CDPATH= cd -- "$(dirname -- "$ENV_FILE")" && pwd)
ENV_FILE="$ENV_DIRECTORY/$(basename -- "$ENV_FILE")"

COMPOSE_DIRECTORY="$DIRECTORY"
SOURCE_CHECKOUT=false
if [[ ! -f "$COMPOSE_DIRECTORY/docker-compose.yml" ]]; then
    COMPOSE_DIRECTORY="$DIRECTORY/../../compose"
    SOURCE_CHECKOUT=true
fi
if [[ ! -f "$COMPOSE_DIRECTORY/docker-compose.yml" || ! -f "$COMPOSE_DIRECTORY/docker-compose-dev.yml" ]]; then
    printf 'Test Compose definitions are missing\n' >&2
    exit 2
fi
# The test directory determines the default project, not the caller's cwd.
# Leave COMPOSE_PROJECT_NAME resolution to Compose, including the env file.
ARGS=(compose --project-directory "$DIRECTORY" --env-file "$ENV_FILE"
      --file "$COMPOSE_DIRECTORY/docker-compose.yml" --file "$COMPOSE_DIRECTORY/docker-compose-dev.yml")
if [[ "$SOURCE_CHECKOUT" == true ]]; then
    export PORTAL_CHECKOUT_ROOT
    PORTAL_CHECKOUT_ROOT=$(CDPATH= cd -- "$DIRECTORY/../../.." && pwd)
    ARGS+=(--file "$COMPOSE_DIRECTORY/docker-compose-checkout.yml")
fi
# Existing test up stays foreground; down never deletes persistent volumes/images.
exec docker "${ARGS[@]}" "$ACTION"
