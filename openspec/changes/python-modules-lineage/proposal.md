# Change: python-modules-lineage

## Why

`extraction_registry` сейчас резолвит Python `PROCESS` через
`importlib` + `get_metadata()`. Это исполняет чужой код в процессе
Portal, ломается на отсутствующих зависимостях ETL и не является
стабильной моделью доверия.

Нужен отдельный AST-адаптер по исходникам loader-модулей (как
`airflow_dags`, но без DAG-семантики) со **своим** корнем исходников —
не `APP_DWH_AIRFLOW_DAGS_ROOT`.

## What Changes

- `extraction_registry` для `Python` / `PythonV0` MUST создавать
  `PROCESS` из `load_options.handlers[]` и MUST NOT вызывать
  `get_metadata()` / `importlib` модуля лоадера.
- Новый встроенный адаптер `python_modules` читает
  `APP_DWH_PYTHON_MODULES_ROOT`, по `attributes.module` уже
  существующего registry `PROCESS` спускается в пакет и через `ast`
  восстанавливает `WRITES_TO` (и при режиме `code` — storage paths).
- Корень DAG (`APP_DWH_AIRFLOW_DAGS_ROOT`) остаётся только для
  `airflow_dags`; смешивать пути MUST NOT.
- REST `GET {url_path}/metadata` без изменений в этом change.
- Публичный HTTP API формы не меняется (только env/settings).

## Approval

`approval_policy: human_required` (ingestion business semantic).

Approved in-session: APR — выключить `get_metadata` для Python;
ввести отдельный PATH для модулей; довести до готовности.

## Capabilities

### Modified Capabilities

- `ingestion`: registry без Python import; адаптер `python_modules`.

## Impact

- `backend/core-service/src/settings/portal.py`
- `backend/core-service/src/domains/catalog/collectors/extraction_registry.py`
- `backend/core-service/src/domains/catalog/providers/extraction_registry.py`
- `backend/core-service/src/domains/catalog/lineage_adapters/**`
- `backend/core-service/tests/unit/test_catalog/**`
- `openspec/specs/ingestion/spec.md`

## Changed scopes

- `openspec/specs/ingestion/**`
- `backend/core-service/src/domains/catalog/**`
- `backend/core-service/src/settings/portal.py`
