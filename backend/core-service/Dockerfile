#=====syntax======docker/dockerfile:1.6===========

FROM 134/python-builder-313:1.0 AS builder

WORKDIR /build

ENV PYTHONPATH="/build:/app/libs" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY ./requirements.txt /app/requirements.txt

RUN python3 -m pip install -U pip \
 && python3 -m pip install --target /app/libs --no-cache-dir -r /app/requirements.txt

COPY ./src/ /app/src/
WORKDIR /app/src
RUN /app/libs/bin/alembic upgrade --sql head > /build/all.sql

# ===============
# ФИНАЛЬНЫЙ ОБРАЗ
# ===============

FROM 134/python-slim-313:1.0

ENV LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH="/app/:/app/src/:/app/libs/"

WORKDIR /app
COPY ./requirements.txt /app/requirements.txt
RUN mkdir -p /app/temp /app/docs /app/migrations
COPY --from=builder /build/all.sql /app/migrations/
COPY --from=builder /app/libs /app/libs

# ВАЖНО: wheelhouse НЕ копируем в image слоем.
# Монтируем его только на время RUN (BuildKit), чтобы не было +157MB слоя.
#RUN --mount=type=bind,source=./wheels,target=/wheels,readonly \
#    python3 -m pip install --no-cache-dir --no-index --find-links=/wheels /wheels/gp134_tools_storage_lib-0.3.81-py3-none-any.whl
#RUN --mount=type=bind,source=./wheels,target=/wheels,readonly \
#    python3 -m pip install --no-cache-dir --no-index --find-links=/wheels /wheels/gp134_tools_storage_olap-0.3.81-py3-none-any.whl

COPY ./src/ /app/src/

# КОПИРУЕМ РАСШИРЕНИЯ: переносит локальную папку в /app/duckdb_extensions внутри контейнера
COPY ./duckdb_extensions/ /app/duckdb_extensions/

CMD ["python3", "src/api/run.py"]
