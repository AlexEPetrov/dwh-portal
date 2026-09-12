# Ingestion

## ADDED Requirements

### Requirement: Lineage собирается независимыми адаптерами

Коллекторы lineage MUST запускаться как независимые адаптеры после
каталожного снимка. Отказ или пропуск одного адаптера MUST NOT отменять
остальные адаптеры и MUST NOT скрывать каталог.

Встроенные адаптеры:

```text
postgres_sql
extraction_registry
airflow_dags
```

Список адаптеров MUST задаваться конфигурацией. Если список не задан,
MUST использоваться `postgres_sql` и `extraction_registry`, а
`airflow_dags` MUST добавляться только при заданном корне исходников DAG.

Дополнительный адаптер MUST загружаться по спецификации `module:Class`
без исполнения DAG-кода и без изменения канонической модели. Неизвестный
или неконструируемый адаптер MUST давать локализованный `FAILED` своего
прогона и MUST NOT останавливать остальные.

Каждый адаптер MUST писать отдельный `collection-status` с именем
адаптера. Пропуск из-за отсутствующего источника MUST быть `SUCCESS` с
явным `skipped` в details, а не `FAILED`.

#### Scenario: Реестр извлечения отсутствует, каталог успешен

- GIVEN в целевой БД нет `sys.data_extraction_sources`
- AND каталожный коллектор завершился успешно
- WHEN запускается ежедневный сбор
- THEN адаптер `extraction_registry` завершается `SUCCESS` со `skipped`
- AND адаптер `postgres_sql` всё равно выполняется
- AND объекты каталога остаются доступны для чтения

#### Scenario: Плагин module:Class подключается

- GIVEN в конфигурации указан адаптер `package.module:ClassName`
- AND класс реализует контракт адаптера lineage
- WHEN запускается ежедневный сбор
- THEN этот адаптер выполняется вместе со встроенными
- AND его ошибки не отменяют прогон `postgres_sql`

### Requirement: SQL lineage между tables и views

Адаптер `postgres_sql` MUST восстанавливать рёбра `DERIVED_FROM` из
системного каталога PostgreSQL для `VIEW` и `MATERIALIZED_VIEW` на
таблицы, представления и материализованные представления, от которых
они зависят.

Рёбра MUST резолвиться к уже снятым каталожным объектам. Нерешённая
зависимость MUST сохраняться как unresolved reference и диагностика
адаптера, а не валить прогон.

`PROCESS` MUST NOT создаваться этим адаптером. `CONTAINS` /
`BELONGS_TO` MUST NOT считаться результатом этого адаптера.

#### Scenario: Представление зависит от таблицы

- GIVEN в каталоге есть таблица `dwh.raw.ice_brent`
- AND представление `dwh.raw.v_ice_brent_latest` зависит от неё в
  PostgreSQL
- WHEN выполняется адаптер `postgres_sql`
- THEN между ними есть ребро `DERIVED_FROM`
- AND `GET /api/v1/assets/{view}/lineage` возвращает оба узла

#### Scenario: База без extraction sources показывает только SQL lineage

- GIVEN `sys.data_extraction_sources` отсутствует
- AND в каталоге есть table→view зависимость
- WHEN клиент запрашивает lineage представления
- THEN в ответе есть SQL-рёбра `DERIVED_FROM`
- AND узлов `EXTRACTION_SOURCE` нет

### Requirement: Обратная цепочка из исходников Airflow

Адаптер `airflow_dags` MUST сканировать локальный корень исходников DAG
как текст и MUST NOT импортировать и MUST NOT исполнять Python DAG.

Для каждой каталожной `TABLE` или `MATERIALIZED_VIEW` адаптер MUST
искать Python-модуль, в котором встречается имя объекта:

- квалифицированное `schema.name` или `database.schema.name` как токен;
- неквалифицированное имя только если оно уникально в каталоге, длиной
  не менее 4 символов и встречается как строковый литерал или токен с
  границами слова;
- имена из стоп-списка (`data`, `table`, `name`, `value`, `type`,
  `date`, `test`, `main`, `config`, `source`, `target`, `user`, `file`,
  `path`, `sql`, `dag`, `task`) MUST NOT сопоставляться неквалифицированно.

`PROCESS` MUST называться по имени модуля файла с конструктором
`DAG(...)` / `@dag(...)` в той же папке. Если конструктора в папке нет,
MUST использоваться модуль, где найдено имя таблицы. `PROCESS` MUST
иметь `WRITES_TO` на сопоставленную таблицу.

В той же папке адаптер MUST искать конструктор `DAG(...)` и MUST
материализовать `EXTRACTION_SOURCE` с `description` из аргумента
`description`, если он есть. `EXTRACTION_SOURCE` MUST иметь `EXTRACTS_TO`
на `PROCESS`.

Адаптер MUST NOT создавать `DATA_SOURCE` и MUST NOT создавать
`STORAGE_LOCATION`. Цепочка Airflow MUST быть:

```text
EXTRACTION_SOURCE -> PROCESS -> TABLE
```

Рёбра представлений `DERIVED_FROM` таблицу MUST писать `postgres_sql`.
Вместе адаптеры MUST образовывать:

```text
EXTRACTION_SOURCE -> PROCESS -> TABLE -> VIEW
```

Несколько папок/DAG на одну таблицу MUST сохраняться как несколько
процессов. Отсутствие корня исходников MUST быть пропуском адаптера,
не `FAILED`.

#### Scenario: Имя модуля DAG становится PROCESS

- GIVEN каталог содержит таблицу `raw.ice_brent`
- AND файл `load_platts_egd.py` содержит токен `raw.ice_brent` и
  `DAG(dag_id="load_platts_egd", description="Загрузка Platts")`
- WHEN выполняется адаптер `airflow_dags`
- THEN создаётся `PROCESS` с именем `load_platts_egd`
- AND создаётся `EXTRACTION_SOURCE` с description «Загрузка Platts»
- AND есть ребро `WRITES_TO` на таблицу
- AND `DATA_SOURCE` и `STORAGE_LOCATION` не создаются

#### Scenario: Пути в DAG не становятся storage

- GIVEN имя таблицы найдено в `load_platts_egd.py`
- AND соседний `paths.py` содержит `"/data/landing/platts/egd"`
- WHEN выполняется адаптер `airflow_dags`
- THEN `STORAGE_LOCATION` не создаётся
- AND цепочка остаётся `EXTRACTION_SOURCE -> PROCESS -> TABLE`

#### Scenario: Корень DAG не задан

- GIVEN `airflow_dags` включён, но корень исходников пуст или отсутствует
- WHEN выполняется адаптер
- THEN прогон `SUCCESS` со `skipped`
- AND каталог и SQL lineage остаются доступны

## MODIFIED Requirements

### Requirement: Канонические identity

Коллекторы MUST использовать устойчивые identity:

- база PostgreSQL: provider + connection identity + имя базы;
- схема: актив базы + имя схемы;
- таблица/представление: актив схемы + имя объекта;
- extraction source: `sys.data_extraction_sources.id`;
- data source из реестра: `sys.data_source_items.id`;
- data source из URL: нормализованный URL без userinfo и query;
- process из реестра: id источника извлечения + стабильный ключ handler;
- process из Airflow: модуль файла с конструктором `DAG(...)` относительно корня DAG;
- extraction source из Airflow: `airflow:{dag_id}` или модуль, если `dag_id` не найден;
- storage location: нормализованный дескриптор расположения.

Секреты, credentials и host-specific детали MUST NOT сохраняться в
Portal DB.

#### Scenario: Storage options без секретов

- GIVEN `storage_options` содержит путь и credentials
- WHEN коллектор материализует `STORAGE_LOCATION`
- THEN в атрибутах остаётся логический `path` и шаблоны
- AND credentials отсутствуют

### Requirement: Source-to-DWH lineage из реестра извлечения

Если `sys.data_extraction_sources` присутствует, адаптер
`extraction_registry` MUST восстанавливать цепочку:

```text
DATA_SOURCE -> EXTRACTION_SOURCE -> STORAGE_LOCATION -> PROCESS -> TABLE
```

`load_options.handlers[]` MUST порождать `PROCESS` для `PythonV0`,
`Python` и `RestApi`. Python-модуль MUST открываться через
`get_metadata()` без инстанцирования loader-класса и без вызова
`entry_point`. REST MUST вызываться как `GET {url_path}/metadata` без
runtime payload.

`writes_to` MUST резолвиться по снимку каталога. Нерешённая цель MUST
сохраняться как unresolved reference и диагностика, а не валить весь
прогон.

Если таблицы `sys.data_extraction_sources` нет, адаптер MUST пропустить
прогон (`SUCCESS` + `skipped`) и MUST NOT удалять SQL- или Airflow-рёбра
других адаптеров.

#### Scenario: Отсутствует get_metadata()

- GIVEN Python-модуль не содержит `get_metadata`
- WHEN коллектор обрабатывает handler
- THEN процесс остаётся видимым
- AND `metadata_status=MISSING`, `lineage_status=UNRESOLVED`
- AND создаётся диагностика, а не глобальный отказ прогона

#### Scenario: REST metadata недоступен

- GIVEN `GET {url_path}/metadata` не отвечает
- WHEN коллектор обрабатывает RestApi handler
- THEN создаётся диагностика по процессу
- AND ранее валидный lineage сохраняется, пока политика stale не скажет иное
- AND остальной каталог остаётся доступен

#### Scenario: Реестр извлечения отсутствует

- GIVEN целевая БД не содержит `sys.data_extraction_sources`
- WHEN адаптер `extraction_registry` запускается
- THEN статус прогона `SUCCESS` со `skipped`
- AND остальные адаптеры lineage продолжают работу
