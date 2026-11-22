# syntax=docker/dockerfile:1

ARG PYTHON_BUILDER_IMAGE=134/python-builder-313:1.0
ARG PYTHON_RUNTIME_IMAGE=134/python-slim-313:1.0
ARG NODE_BUILD_IMAGE=node:22.21.1-bookworm-slim

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
COPY frontend/scripts/ ./scripts/
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
# Offline SQL compilation only; never connects to a database or applies migrations.
RUN mkdir -p /build && /app/libs/bin/alembic upgrade --sql head > /build/all.sql

FROM ${PYTHON_RUNTIME_IMAGE} AS portal
USER 0
ENV LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app:/app/src:/app/libs \
    APP_API_PORT=5051
WORKDIR /app
COPY --from=backend /app/libs/ /app/libs/
COPY --from=backend /build/all.sql /app/migrations/all.sql
COPY backend/core-service/requirements.txt /app/requirements.txt
COPY backend/core-service/src/ /app/src/
COPY backend/core-service/duckdb_extensions/ /app/duckdb_extensions/
COPY --from=frontend /build/frontend/web/dist/ /app/frontend-dist/
COPY infra/images/portal/diagnose_db.py /opt/portal/diagnose_db.py
RUN python3 -c "import os; from pathlib import Path; paths = ['/app/temp', '/app/docs', '/app/logs', '/app/local_storage']; [(Path(p).mkdir(parents=True, exist_ok=True), os.chown(p, 1001, 0)) for p in paths]"
USER 1001:0
# MCP belongs to Portal. Its application defaults remain disabled in this base.
EXPOSE 5051
CMD ["python3", "src/api/run.py"]
