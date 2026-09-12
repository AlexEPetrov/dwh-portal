# Catalog

## ADDED Requirements

### Requirement: Lineage доступен без extraction sources

`GET /api/v1/assets/{asset_id}/lineage` MUST возвращать граф по всем
сохранённым рёбрам данных, независимо от того, какой адаптер их создал.

Если реестр извлечения отсутствует, карточка таблицы или представления
MUST всё равно показывать SQL-зависимости `DERIVED_FROM` между
`TABLE` / `VIEW` / `MATERIALIZED_VIEW`. Узлы `DATA_SOURCE` /
`EXTRACTION_SOURCE` / `PROCESS` MUST появляться только если их создал
другой адаптер (реестр или Airflow).

Нерешённые цели MUST отображаться явно и MUST NOT скрываться.

#### Scenario: Lineage представления только из SQL

- GIVEN в Portal DB нет extraction sources
- AND представление `dwh.raw.v_ice_brent_latest` имеет ребро
  `DERIVED_FROM` к `dwh.raw.ice_brent`
- WHEN клиент запрашивает lineage представления
- THEN ответ содержит оба объекта и ребро `DERIVED_FROM`
- AND ответ не содержит `EXTRACTION_SOURCE`

#### Scenario: Lineage таблицы из Airflow DAG

- GIVEN процесс DAG пишет в таблицу и связан с extraction source
- WHEN клиент запрашивает lineage таблицы
- THEN в ответе есть `EXTRACTION_SOURCE`, `PROCESS` и `TABLE`
- AND рёбра только data-flow типов
- AND `DATA_SOURCE` и `STORAGE_LOCATION` отсутствуют

#### Scenario: Lineage представления через DAG и SQL

- GIVEN представление имеет `DERIVED_FROM` на таблицу
- AND процесс DAG пишет в эту таблицу и связан с extraction source
- WHEN клиент запрашивает lineage представления
- THEN в ответе есть `EXTRACTION_SOURCE`, `PROCESS`, `TABLE` и `VIEW`
- AND `DATA_SOURCE` и `STORAGE_LOCATION` отсутствуют
