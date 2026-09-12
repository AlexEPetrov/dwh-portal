# Change: lineage-source-adapters

## Why

Сейчас source-to-DWH lineage восстанавливается только из
`sys.data_extraction_sources`. На базе без этого реестра прогон lineage
падает, а граф между tables/views из системного каталога PostgreSQL не
строится. Портал должен работать универсально: SQL-зависимости всегда,
реестр извлечения — если он есть, код Airflow — как отдельный подключаемый
источник.

## What Changes

- Коллекция lineage становится набором независимых адаптеров (built-in и
  динамически загружаемые `module:Class`).
- Встроенный адаптер `postgres_sql` восстанавливает `VIEW` /
  `MATERIALIZED_VIEW` `DERIVED_FROM` таблицы и другие представления из
  `pg_depend`.
- Адаптер `extraction_registry` остаётся прежней цепочкой
  `DATA_SOURCE -> EXTRACTION_SOURCE -> STORAGE_LOCATION -> PROCESS -> TABLE`,
  но MUST NOT валить прогон, если реестра нет: статус SUCCESS со
  `skipped=true`.
- Адаптер `airflow_dags` (опционально) разбирает исходники DAG через
  `ast`, идёт от конструктора DAG по локальным импортам и пишет
  `EXTRACTION_SOURCE (DAG) -> PROCESS (DAG) -> TABLE`. Режим
  `catalog` (по умолчанию) линкует только таблицы из снимка каталога;
  режим `code` материализует цели из AST, включая unresolved.
  Переключение: `APP_DWH_AIRFLOW_LINEAGE_MODE`, CLI и
  `POST /api/v1/collect`.
- `POST /api/v1/collect` запускает тот же сбор, что CLI, с флагами
  `reset` и `airflow_lineage_mode` (вызов из Airflow DAG).
- Для `EXTRACTION_SOURCE` из таблицы реестра (не DAG) Portal API
  постранично читает фактически загруженные файлы из `sys.log_files`.
  Каталог и lineage-граф по-прежнему из снимков; файлы не становятся
  узлами графа. UI — вкладка «Загрузки».
- Каноническая модель, Portal API чтения lineage и UI не меняют форму
  контракта чтения: новые рёбра вливаются в уже существующие типы
  `DERIVED_FROM` / `READS_FROM` / `WRITES_TO`. Collect HTTP — аддитивный
  операторский метод; `/loads` — аддитивное live-чтение журнала.

Нет **BREAKING** изменений публичного HTTP API.

## Capabilities

### New Capabilities

- нет. Новые capability paths не создаются; `openspec/capabilities.yaml`
  уже содержит `catalog` и `ingestion`.

### Modified Capabilities

- `ingestion`: коллекторы lineage — адаптеры; отсутствие extraction
  registry не является отказом всего lineage; SQL-зависимости и
  Airflow reverse reconstruction.
- `catalog`: lineage на карточке MUST отображаться и без extraction
  sources, если есть рёбра tables/views (и опционально Airflow);
  registry extraction source MUST показывать постраничные загрузки.

## Impact

- `backend/core-service/src/domains/catalog/lineage_adapters/**` (новый пакет)
- `backend/core-service/src/domains/catalog/collectors/runner.py`
- `backend/core-service/src/domains/catalog/collectors/extraction_registry.py`
- `backend/core-service/src/domains/catalog/providers/postgres.py`
- `backend/core-service/src/domains/catalog/providers/extraction_registry.py`
- `backend/core-service/src/settings/portal.py`
- `backend/core-service/src/api/portal/**`
- `backend/core-service/tests/unit/test_catalog/**`
- current specs `openspec/specs/ingestion/spec.md`, `openspec/specs/catalog/spec.md`
- frontend catalog lineage consumers — без смены generated API, если
  граф по-прежнему читается через `GET /api/v1/assets/{id}/lineage`

Публичный OpenAPI и generated client не обязаны меняться: список
collection-status уже произвольный по `collector_name`.

## Changed scopes

- `openspec/specs/catalog/**`, `openspec/specs/ingestion/**`
- `backend/core-service/src/domains/catalog/**`

## Change types

- `business_or_contract_semantic` — новые источники lineage, режимы
  Airflow `catalog`/`code` и правило «реестр необязателен»
- `public_api_semantic` — аддитивный `POST /api/v1/collect` и
  `GET /api/v1/assets/{id}/loads`

## Applicable routing

- topics: `catalog`, `ingestion`
- workflow: `SPEC-WF-HIGH-RISK-SEMANTICS` (consumer-visible lineage meaning)
- contract `http-api`: `SPEC-WF-API-CONTRACT` из-за `POST /api/v1/collect`
- `approval_policy`: `human_required` по классу бизнес-семантики и
  публичному HTTP

## Approval

Пользователь явно поручил два переключаемых режима Airflow lineage
(`catalog` / `code`) и HTTP-метод collect с этими флагами для вызова
из DAG. Затем поручил вкладку «Загрузки» с paging по `sys.log_files`
для extraction source из реестра (не DAG).

## Downstream

Generated OpenAPI/frontend client входят в цепочку из-за
`POST /api/v1/collect` и `GET /api/v1/assets/{id}/loads`.
Verification: `CORE-PYTEST-TARGET` для `tests/unit/test_catalog`,
затем `OPENAPI-EXPORT` и `FRONTEND-GEN-API`.
