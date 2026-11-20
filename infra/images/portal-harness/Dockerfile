# syntax=docker/dockerfile:1

ARG PYTHON_BUILDER_IMAGE=134/python-builder-313:1.0
ARG PYTHON_RUNTIME_IMAGE=134/python-slim-313:1.0
ARG NODE_BUILD_IMAGE=node:22.21.1-bookworm-slim
ARG DSH_BUILD_IMAGE=node:24.22.2-bookworm

FROM ${NODE_BUILD_IMAGE} AS frontend
WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
COPY frontend/web/package.json ./web/package.json
COPY frontend/ui-kit/package.json ./ui-kit/package.json
COPY frontend/app-shell/package.json ./app-shell/package.json
RUN npm ci --no-audit --no-fund
COPY frontend/web/ ./web/
COPY frontend/ui-kit/ ./ui-kit/
COPY frontend/app-shell/ ./app-shell/
COPY common/contracts/jsonschema/ /build/common/contracts/jsonschema/
# No host .env files enter this build; generated requests use the Portal origin.
ENV VITE_API_BASE_URL=/api
RUN cd web && npm run build

FROM ${PYTHON_BUILDER_IMAGE} AS backend
USER 0
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app:/app/src:/app/libs
WORKDIR /app
COPY backend/core-service/requirements.txt ./requirements.txt
RUN python3 -m pip install --target /app/libs --no-cache-dir -r requirements.txt
COPY backend/core-service/src/ ./src/
WORKDIR /app/src
RUN mkdir -p /build && /app/libs/bin/alembic upgrade --sql head > /build/all.sql

FROM ${DSH_BUILD_IMAGE} AS harness
USER 0
WORKDIR /build
ENV CI=true \
    DSH_TELEMETRY_DISABLED=1
COPY infra/images/portal-harness/build_dsh.py infra/images/portal-harness/materialize_dsh.mts infra/images/portal-harness/dsh-source.json ./
RUN python3 build_dsh.py

FROM ${PYTHON_RUNTIME_IMAGE} AS runtime
USER 0
ENV LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    HOME=/var/lib/dsh \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app:/app/src:/app/libs \
    APP_API_PORT=5051 \
    DSH_PORT=3080 \
    DSH_HOME=/var/lib/dsh \
    DSH_AGENTS_HOME=/var/lib/dsh/agents \
    DSH_TELEMETRY_DISABLED=1
WORKDIR /app
COPY --from=backend /app/libs/ /app/libs/
COPY --from=backend /build/all.sql /app/migrations/all.sql
COPY backend/core-service/requirements.txt /app/requirements.txt
COPY backend/core-service/src/ /app/src/
COPY backend/core-service/duckdb_extensions/ /app/duckdb_extensions/
COPY --from=frontend /build/frontend/web/dist/ /app/frontend-dist/
COPY --from=harness /usr/local/bin/node /usr/local/bin/node
COPY --from=harness /usr/local/LICENSE /opt/node-LICENSE
COPY --from=harness /opt/dsh/ /opt/dsh/
COPY infra/images/portal-harness/dsh /usr/local/bin/dsh
COPY infra/images/portal-harness/launch.py infra/images/portal-harness/check_dsh_cli.py infra/images/portal-harness/check_dsh_cli.mjs infra/images/portal-harness/dsh-parser-loader.mjs infra/images/portal-harness/healthcheck.py infra/images/portal-harness/container_smoke.py infra/images/portal-harness/dsh.patch.yml infra/images/portal-harness/dsh-guard.mjs infra/images/portal-harness/dsh-source.json infra/images/portal-harness/agent-context.md /opt/portal-harness/
COPY infra/images/portal-harness/tests/test_dsh_parser_loader.mjs /opt/portal-harness/tests/test_dsh_parser_loader.mjs
RUN python3 -c "import os; from pathlib import Path; paths = ['/app/temp', '/app/docs', '/app/logs', '/app/local_storage', '/var/lib/dsh', '/var/lib/dsh/workspace']; [(Path(p).mkdir(parents=True, exist_ok=True), os.chown(p, 1001, 0)) for p in paths]; os.chmod('/usr/local/bin/dsh', 0o755)"
USER 1001:0
# Deliberately fail the build on incompatible UBI8/glibc or incomplete bundles.
RUN node --version && dsh --version && dsh --profile web --patch /opt/portal-harness/dsh.patch.yml --dump-config
RUN node --test /opt/portal-harness/tests/test_dsh_parser_loader.mjs && python3 /opt/portal-harness/check_dsh_cli.py
EXPOSE 5051 3080
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD ["python3", "/opt/portal-harness/healthcheck.py"]
ENTRYPOINT ["python3", "/opt/portal-harness/launch.py"]
CMD ["all"]
