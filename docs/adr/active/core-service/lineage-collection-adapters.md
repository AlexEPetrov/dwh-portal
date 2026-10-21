# ADR: Сбор lineage через набор независимых adapters

## Status

Accepted

## Context

MVP изначально строил source-to-DWH lineage из `sys.data_extraction_sources`.
Параллельно появилось требование универсальности: портал должен работать и на
DWH **без** extraction registry — тогда lineage ограничен связями
tables/views внутри БД. Второй уровень — восстановление цепочки из исходников
Airflow (имя таблицы в DAG → loader process → URL/data source).

В коде уже есть pluggable adapters (`postgres_sql`, `extraction_registry`,
`python_modules`, `airflow_dags`) под единым протоколом. Это решение нужно
зафиксировать как архитектурный контракт домена `catalog`, а не как
временную деталь реализации.

## Decision

### 1. Lineage — ответственность `catalog`

Сбор и хранение data-flow рёбер живут в `domains/catalog` (read-модель).
Admin/documents не строят lineage-граф; они могут лишь влиять на источники,
из которых adapters потом читают.

### 2. Multi-adapter collection

Каждый источник lineage — отдельный adapter с протоколом:

```text
name: str
collect(now) -> CollectionRun
```

Adapters независимы: сбой одного даёт diagnostic / FAILED|PARTIAL run и не
валидирует остальные. Список adapters конфигурируем
(`APP_DWH_LINEAGE_ADAPTERS`); по умолчанию включаются все built-in.

Built-in:

| Adapter | Что даёт |
|---|---|
| `postgres_sql` | зависимости TABLE/VIEW внутри PostgreSQL |
| `extraction_registry` | цепочка DATA_SOURCE → EXTRACTION_SOURCE → STORAGE → PROCESS → TABLE |
| `python_modules` | `get_metadata()` / writes_to для Python loaders |
| `airflow_dags` | обратный разбор DAG: table name в коде → process → URL/data source |

### 3. Режимы развёртывания

- **С registry:** полный source-to-DWH граф; registry adapter активен.
- **Без registry:** `extraction_registry` пропускается или даёт skipped run;
  пользовательский lineage остаётся полезным за счёт `postgres_sql` (+ при
  наличии корня — `airflow_dags` / `python_modules`).
- Граф может быть неполным; unresolved targets показываются явно.

### 4. Каноническая модель не меняется

Все adapters пишут в одни и те же `Asset` / `Relationship` /
`DISCOVERY_DIAGNOSTIC`. UI читает только Portal API lineage endpoints и не
знает, какой adapter создал ребро.

### 5. Presentation (UI) отдельно от collection

Режимы UI (list / map / universe) — представления одного API. Они не добавляют
семантики рёбер и не принадлежат доменам admin/documents.

## Consequences

- Новые источники lineage добавляются новым adapter'ом (или `module:Class`),
  а не ветвлением в UI.
- Отключение registry — конфигурация adapters, а не отдельная «редакция»
  продукта.
- Поведенческие требования к каждому adapter'у уточняются в
  `openspec/specs/ingestion/spec.md` / `catalog/spec.md` при изменении
  контракта.

## Related

- `docs/adr/active/ADR-002-mvp-metadata-lineage.md`
- `docs/adr/active/core-service/portal-business-domains.md`
- `domains/catalog/lineage_adapters/`
