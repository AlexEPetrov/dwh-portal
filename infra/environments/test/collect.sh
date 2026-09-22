#!/usr/bin/env bash
# Run portal catalog collect in the target Docker environment.
#
# From .build/<env>/ (compose + .env next to this script after build_env_test):
#
#   ./collect.sh
#   ./collect.sh --reset
#   ./collect.sh --airflow-lineage-mode code
#   ./collect.sh --api
#   ./collect.sh --api --reset --airflow-lineage-mode catalog
#
# Modes:
#   (default) CLI in core-service: python3 -m domains.catalog.collect
#   --api     HTTP POST /api/v1/collect (Swagger: runPortalCollect)
#
# Env values come from ./.env via docker compose --env-file.

set -euo pipefail
cd "$(dirname "$0")"

COMPOSE=(docker compose --env-file ./.env -f ./docker-compose.yml)
USE_API=0
RESET=0
AIRFLOW_MODE=""
PASSTHROUGH=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --api)
      USE_API=1
      shift
      ;;
    --reset)
      RESET=1
      PASSTHROUGH+=(--reset)
      shift
      ;;
    --airflow-lineage-mode)
      AIRFLOW_MODE="${2:-}"
      if [[ -z "$AIRFLOW_MODE" ]]; then
        echo "--airflow-lineage-mode requires catalog|code" >&2
        exit 2
      fi
      PASSTHROUGH+=(--airflow-lineage-mode "$AIRFLOW_MODE")
      shift 2
      ;;
    --airflow-lineage-mode=*)
      AIRFLOW_MODE="${1#*=}"
      PASSTHROUGH+=(--airflow-lineage-mode "$AIRFLOW_MODE")
      shift
      ;;
    -h|--help)
      sed -n '2,16p' "$0"
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      exit 2
      ;;
  esac
done

if [[ "$USE_API" -eq 1 ]]; then
  set -a
  # shellcheck disable=SC1091
  source ./.env
  set +a

  host_port="${APP_API_HOST_PORT:-5052}"
  url="http://127.0.0.1:${host_port}/api/v1/collect"
  query=()
  [[ "$RESET" -eq 1 ]] && query+=("reset=true")
  [[ -n "$AIRFLOW_MODE" ]] && query+=("airflow_lineage_mode=${AIRFLOW_MODE}")
  if [[ ${#query[@]} -gt 0 ]]; then
    qs=$(IFS='&'; echo "${query[*]}")
    url="${url}?${qs}"
  fi

  echo "POST ${url}" >&2
  curl -fsS -X POST "$url" -H 'Content-Type: application/json' -d '{}'
  echo
  exit 0
fi

running="$("${COMPOSE[@]}" ps --status running --services 2>/dev/null || true)"
if grep -qx 'core-service' <<<"$running"; then
  echo "collect via docker compose exec core-service" >&2
  "${COMPOSE[@]}" exec -T core-service \
    python3 -m domains.catalog.collect "${PASSTHROUGH[@]+"${PASSTHROUGH[@]}"}"
else
  echo "core-service not running; collect via docker compose run --rm" >&2
  "${COMPOSE[@]}" run --rm --no-deps core-service \
    python3 -m domains.catalog.collect "${PASSTHROUGH[@]+"${PASSTHROUGH[@]}"}"
fi
