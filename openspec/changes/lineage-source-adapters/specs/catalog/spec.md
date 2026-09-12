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

### Requirement: Корень lineage по умолчанию

`GET /api/v1/lineage/roots` MUST возвращать все активные `DATA_SOURCE` и
`EXTRACTION_SOURCE` без родительского `DATA_SOURCE`. Страница `/lineage`
без выбранного объекта MUST показывать этот набор.

#### Scenario: Обзор корней на /lineage

- GIVEN есть `DATA_SOURCE` ICE и Airflow extraction source без родителя
- WHEN клиент вызывает `GET /api/v1/lineage/roots`
- THEN в узлах есть оба корня
- AND registry extraction source с родителем ICE отсутствует

### Requirement: Браузер говорит только с Portal API

Веб-приложение MUST читать каталог только через `/api/v1/*`.
UI MUST NOT вызывать `POST /api/v1/collect`.

### Requirement: Загрузки EXTRACTION_SOURCE из реестра

Для `EXTRACTION_SOURCE` с `source_provider=extraction_registry`
`GET /api/v1/assets/{asset_id}/loads` MUST возвращать постраничный список
файлов из `sys.log_files` по `extraction_source_id`, сортировка по времени
загрузки DESC. Файлы MUST NOT становиться узлами lineage-графа.

Для Airflow DAG и при отсутствии `sys.log_files` ответ MUST быть пустым
с `available=false`, не 500. UI MUST показывать вкладку «Загрузки» на
карточке и на странице Lineage.

#### Scenario: Страница загрузок постранично

- GIVEN extraction source из реестра с несколькими строками в `sys.log_files`
- WHEN клиент запрашивает `/loads?page=1&page_size=50`
- THEN ответ содержит не более 50 файлов и `available=true`

#### Scenario: Airflow extraction source без журнала загрузок

- GIVEN `EXTRACTION_SOURCE` с `source_provider=airflow_dags`
- WHEN клиент запрашивает `/loads`
- THEN `items` пустой и `available=false`
