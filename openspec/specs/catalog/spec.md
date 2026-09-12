# Каталог объектов DWH Portal

## Purpose

DWH Portal даёт аналитику и инженерам единый каталог объектов хранилища:
поиск таблиц и представлений, карточка объекта с описанием колонок,
оценкой размера, происхождением данных и историей структурных изменений.
Каталог читает только нормализованные снимки Portal API и не сканирует DWH
в момент открытия страницы.

## Requirements

### Requirement: Каноническая модель вместо провайдерных DTO

Portal API MUST возвращать каноническую продуктовую модель (`Asset`,
`AssetColumn`, `Relationship`, `ChangeEvent`, агрегаты overview/storage).
API MUST NOT отдавать строки системного каталога PostgreSQL, JSON
`sys.data_extraction_sources` или сущности OpenMetadata как основной контракт.

#### Scenario: Список объектов содержит канонические поля

- GIVEN в Portal DB есть таблица с квалифицированным именем `dwh.raw.ice_brent`
- WHEN клиент вызывает `GET /api/v1/assets`
- THEN ответ содержит `id`, `asset_type`, `qualified_name`, `name`,
  `description`, `status` и сведения о размере из последнего снимка
- AND ответ не содержит сырых полей `extract_options` / `load_options`

### Requirement: Просмотр и фильтрация объектов

`GET /api/v1/assets` MUST поддерживать поиск `q`, фильтры `database`,
`schema`, `type`, `source`, `status`, `changed_since`, сортировку `sort`
и пагинацию `page` / `page_size`.

Допустимые начальные `asset_type`:

```text
DATABASE
SCHEMA
TABLE
VIEW
MATERIALIZED_VIEW
DATA_SOURCE
EXTRACTION_SOURCE
STORAGE_LOCATION
PROCESS
```

`status=active` MUST исключать soft-deleted объекты. Удалённый объект
MUST оставаться доступным по идентификатору для истории.

#### Scenario: Пагинация списка таблиц

- GIVEN в каталоге больше одной страницы таблиц
- WHEN клиент запрашивает `type=TABLE&page=1&page_size=50`
- THEN ответ содержит не более 50 элементов и общее число совпадений

#### Scenario: Поиск по имени

- GIVEN есть объект `dwh.raw.ice_brent`
- WHEN клиент запрашивает `q=ice_brent`
- THEN объект присутствует в результатах

### Requirement: Карточка объекта

`GET /api/v1/assets/{asset_id}` MUST возвращать карточку объекта.
`GET /api/v1/assets/{asset_id}/columns` MUST возвращать колонки в порядке
`ordinal` с типом, nullable и описанием.

Если у объекта есть `source_files`, список и карточка MUST показывать
эти пути: из какого файла DAG объект был разобран.

#### Scenario: Колонки таблицы

- GIVEN у таблицы есть колонки `trade_date` и `settlement_price`
- WHEN клиент запрашивает колонки объекта
- THEN они возвращаются в порядке `ordinal` вместе с `data_type` и `description`

#### Scenario: Карточка показывает source_files

- GIVEN объект создан адаптером `airflow_dags` из `platts_egd/paths.py`
- WHEN клиент открывает карточку
- THEN в ответе есть `source_files` с `platts_egd/paths.py`

### Requirement: Lineage на карточке и отдельной странице

`GET /api/v1/assets/{asset_id}/lineage` MUST возвращать ограниченный
обход вверх и вниз только по рёбрам данных:

```text
EXTRACTS_TO
READS_FROM
WRITES_TO
DERIVED_FROM
```

`CONTAINS`, `BELONGS_TO` и `PARENT_OF` MUST NOT считаться lineage-рёбрами.
Нерешённые цели MUST отображаться явно и MUST NOT скрываться.

#### Scenario: Нерешённая цель видна

- GIVEN процесс пишет в таблицу, которой нет в каталоге
- WHEN клиент запрашивает lineage процесса
- THEN в ответе есть нерешённая цель с исходной ссылкой `database.schema.name`

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

### Requirement: Обзор, хранение и изменения

`GET /api/v1/overview` MUST возвращать число объектов, итоги хранения,
сводку изменений и свежесть коллекторов.

`GET /api/v1/storage` и `GET /api/v1/storage/history` MUST отдавать
агрегаты и историю из снимков, а не live-запросы к DWH.

`GET /api/v1/changes` и `GET /api/v1/changes/{change_id}` MUST отдавать
события `ADDED`, `REMOVED`, `RENAMED`, `STRUCTURE_CHANGED`,
`DESCRIPTION_CHANGED`.

Каждая пользовательская страница, зависящая от снимков, MUST получать
сведения о свежести коллекторов.

#### Scenario: Overview не сканирует DWH

- GIVEN последние снимки уже сохранены в Portal DB
- WHEN клиент вызывает `GET /api/v1/overview`
- THEN ответ собирается только из снимков Portal DB

### Requirement: Браузер говорит только с Portal API

Веб-приложение MUST читать каталог, хранение, lineage и изменения
только через `/api/v1/*`. UI MUST NOT выполнять metadata-сканирование DWH
и MUST NOT вызывать `POST /api/v1/collect`. Операторский сбор запускает
Airflow или CLI.

#### Scenario: Страница объектов использует канонический список

- GIVEN пользователь открывает Objects
- WHEN страница загружает данные
- THEN она вызывает `GET /api/v1/assets` и отображает результат
