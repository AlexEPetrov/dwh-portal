# ADR: Сбор lineage через набор независимых adapters

## Status

Accepted

Updated: 2026-10-24

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

Сбор и хранение рёбер логической схемы потока живут в `domains/catalog`
(read-модель). Это не граф конкретного выполнения и не журнал RunEvent.
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
| `extraction_registry` | определения источников, storage и PROCESS; REST metadata; Python-цели дополняются отдельным discovery |
| `python_modules` | AST исходников Python loaders из отдельного корня; дописывает WRITES_TO существующим registry PROCESS без импорта loader |
| `airflow_dags` | обратный разбор DAG: table name в коде → process → URL/data source |

### 3. Режимы развёртывания

- **С registry:** source-to-DWH граф в пределах доступных метаданных;
  registry adapter активен, полнота не гарантируется.
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

### 6. AST и явные контракты — дополняющие способы discovery

AST — поддерживаемый источник логической схемы, а не исключительно временный
fallback. Он извлекает связи из известного набора конструкций без исполнения
loader/DAG и может работать до первой загрузки. Стоимость поддержки и
проверяемое покрытие определяют его дальнейшее применение.

`get_metadata()` / `get_metadata(config)` — другой поддерживаемый способ:
handler явно объявляет зависимости, метод вызывается отдельно от `load_file()`
до первого запуска. Для него необходимы безопасный импорт, отсутствие
побочных эффектов и воспроизводимость для версии кода и конфигурации.

Подключение явного Python-контракта в основной collection pipeline является
планируемым изменением. Текущая реализация registry не импортирует Python
loaders, а `python_modules` использует AST; это ограничение действующих specs
не отменяется одной правкой ADR.

Способы дают свидетельства с происхождением и областью действия. Совпавшие
свидетельства могут подтверждать одну логическую связь; расхождения и
неоднозначность диагностируются, а не скрываются. Универсальный безусловный
приоритет одного способа этим решением не вводится.

### 7. Выполнения и OpenLineage

Будущий receiver хранит исходные RunEvent и сведения о запусках отдельно от
`Asset` / `Relationship`. Он не добавляется как adapter, молча смешивающий
исторические выполнения с текущей схемой. Наблюдение выполнения может служить
свидетельством зависимости, но отсутствие связи в одном запуске не удаляет её
из схемы. Подробное решение находится в ADR-002, разделах 3.4–3.5 и 17.1.

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
