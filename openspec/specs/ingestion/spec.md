# Наполнение каталога снимками

## Purpose

Коллекторы периодически собирают операционные метаданные DWH, реестра
загрузки и логического хранения, сохраняют канонические снимки и
диагностику. Это позволяет порталу показывать каталог, размеры, lineage
и изменения без metadata-сканирования в момент открытия страницы.
Журнал фактически загруженных файлов (`sys.log_files`) в снимок не
копируется: его читает Portal API постранично.

## Requirements

### Requirement: Снимочный сбор отдельно от чтения API

Коллекторы MUST выполняться вне пользовательского запроса страницы.
Нормальный путь `UI -> Portal API -> Portal DB` MUST NOT запускать
полное сканирование DWH.

Операторский запуск MUST быть доступен через CLI
`python -m domains.catalog.collect` и через `POST /api/v1/collect`,
чтобы Airflow DAG мог инициировать снимочный сбор. Этот путь MUST
запускать полный сбор и MUST NOT вызываться страницами UI.

Коллектор каталога MUST читать PostgreSQL system catalog через
выделенное read-only соединение и MUST NOT выполнять `COUNT(*)` по
крупным таблицам только ради UI.

Коллекторы MUST NOT копировать `sys.log_files` в Portal DB. Фактически
загруженные файлы registry `EXTRACTION_SOURCE` читаются live и
постранично через `GET /api/v1/assets/{asset_id}/loads`.

#### Scenario: Повторный запуск идемпотентен

- GIVEN объект уже есть в Portal DB с тем же каноническим identity
- WHEN коллектор запускается повторно
- THEN новый канонический `Asset` не создаётся только из-за смены
  отображаемого имени
- AND обновляются `last_seen_at` и связанные снимки

### Requirement: Опциональный сброс снимков перед сбором

Сбор MUST поддерживать явный сброс Portal DB перед прогоном. Сброс MUST
удалять только снимки схемы `sol_dwh_portal` и MUST NOT изменять
сканируемый DWH.

Сброс MUST включаться флагом `--reset`, полем `reset` в
`POST /api/v1/collect` или `APP_PORTAL_RESET_ON_COLLECT=true` и MUST
быть выключен по умолчанию.

#### Scenario: Collect с --reset очищает старый lineage

- GIVEN в Portal DB остались `DATA_SOURCE` от предыдущего адаптера
- WHEN запускается `python -m domains.catalog.collect --reset`
- THEN предыдущие снимки удалены до нового прогона
- AND новый прогон записывает только текущие адаптеры

### Requirement: Канонические identity

Коллекторы MUST использовать устойчивые identity:

- база PostgreSQL: provider + connection identity + имя базы;
- схема: актив базы + имя схемы;
- таблица/представление: актив схемы + имя объекта;
- extraction source: `sys.data_extraction_sources.id`;
- data source из реестра: `sys.data_source_items.id`;
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

### Requirement: Lineage собирается независимыми адаптерами

Коллекторы lineage MUST запускаться как независимые адаптеры после
каталожного снимка. Отказ или пропуск одного адаптера MUST NOT отменять
остальные адаптеры и MUST NOT скрывать каталог.

Встроенные адаптеры:

```text
postgres_sql
extraction_registry
python_modules
airflow_dags
```

Список адаптеров MUST задаваться конфигурацией. Если список не задан,
MUST использоваться перечисленные встроенные имена. `airflow_dags` и
`python_modules` без своих корней MUST завершаться `SUCCESS` со
`skipped`, а не исключаться из пайплайна молча без записи статуса.

Дополнительный адаптер MUST загружаться по спецификации `module:Class`
без исполнения DAG/loader-кода и без изменения канонической модели.
Неизвестный или неконструируемый адаптер MUST давать локализованный
`FAILED` своего прогона и MUST NOT останавливать остальные.

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

### Requirement: Source-to-DWH lineage из реестра извлечения

Если `sys.data_extraction_sources` присутствует, адаптер
`extraction_registry` MUST восстанавливать цепочку:

```text
DATA_SOURCE -> EXTRACTION_SOURCE -> STORAGE_LOCATION -> PROCESS
```

`load_options.handlers[]` MUST порождать `PROCESS` для `PythonV0`,
`Python` и `RestApi`.

Для `Python` / `PythonV0` адаптер MUST NOT вызывать `get_metadata()`
и MUST NOT импортировать модуль лоадера. PROCESS MUST сохранять
`attributes.module` и получать `metadata_status=DEFERRED` и
`lineage_status=UNRESOLVED`, пока цели записи не допишет адаптер
`python_modules` (или пока оператор не смонтирует корень).

Для `RestApi` MUST вызываться `GET {url_path}/metadata` без runtime
payload; `writes_to` из REST MUST резолвиться по снимку каталога как
раньше.

Нерешённая цель MUST сохраняться как unresolved reference и
диагностика, а не валить весь прогон.

Если таблицы `sys.data_extraction_sources` нет, адаптер MUST пропустить
прогон (`SUCCESS` + `skipped`) и MUST NOT удалять SQL-, Python-module-
или Airflow-рёбра других адаптеров.

#### Scenario: Python handler без исполнения модуля

- GIVEN Python handler с `module=company.loaders.brent`
- WHEN коллектор `extraction_registry` обрабатывает handler
- THEN PROCESS создаётся
- AND `metadata_status=DEFERRED`, `lineage_status=UNRESOLVED`
- AND модуль не импортируется
- AND глобальный отказ прогона не происходит

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

### Requirement: Python module lineage из отдельного корня исходников

Адаптер `python_modules` MUST сканировать локальный корень
`APP_DWH_PYTHON_MODULES_ROOT` через синтаксический разбор (`ast`) и
MUST NOT импортировать и MUST NOT исполнять код loader-модулей.

Корень MUST быть отдельным от `APP_DWH_AIRFLOW_DAGS_ROOT`. Адаптер
MUST NOT читать Airflow DAG root для резолва registry PROCESS.

Адаптер MUST брать уже существующие `PROCESS` с
`source_provider=extraction_registry` и `handler_type` в
`Python` / `PythonV0`, у которых задан `attributes.module`.
Адаптер MUST NOT создавать новый `PROCESS` или `EXTRACTION_SOURCE`.

По dotted `module` адаптер MUST резолвить файл под корнем
(`a.b.c` → `a/b/c.py` или пакет с `__init__.py`), строить замыкание
локальных импортов под этим корнем (те же правила пропуска сторонних
пакетов, что у Airflow AST) и восстанавливать `WRITES_TO` при
свидетельстве записи и идентичности таблицы.

Режим сопоставления MUST задаваться
`APP_DWH_PYTHON_MODULES_LINEAGE_MODE` со значениями `catalog` (по
умолчанию) и `code`, с семантикой, аналогичной
`APP_DWH_AIRFLOW_LINEAGE_MODE`.

Отсутствие корня MUST быть пропуском адаптера (`SUCCESS` + `skipped`),
не `FAILED`. Отсутствие файла модуля под корнем MUST оставлять
PROCESS видимым, писать диагностику на PROCESS и MUST NOT валить
прогон.

#### Scenario: Registry PROCESS получает WRITES_TO из AST модулей

- GIVEN `APP_DWH_PYTHON_MODULES_ROOT` указывает на дерево с модулем
  `loaders.ice_brent`
- AND registry создал PROCESS с `module=loaders.ice_brent`
- AND в модуле есть свидетельство записи в `raw.ice_brent`
- AND таблица есть в снимке каталога
- WHEN выполняется адаптер `python_modules` в режиме `catalog`
- THEN у того же PROCESS есть ребро `WRITES_TO` на таблицу
- AND новый PROCESS не создаётся

#### Scenario: Корень модулей не задан

- GIVEN `APP_DWH_PYTHON_MODULES_ROOT` пуст
- WHEN выполняется адаптер `python_modules`
- THEN статус прогона `SUCCESS` со `skipped`
- AND рёбра registry PROCESS не меняются этим адаптером

### Requirement: Обратная цепочка из исходников Airflow

Адаптер `airflow_dags` MUST сканировать локальный корень исходников DAG
через синтаксический разбор (`ast`) и MUST NOT импортировать и MUST NOT
исполнять Python DAG. Неразбираемый файл MUST пропускаться.

Адаптер MUST начинать с модулей, где есть конструктор `DAG(...)` /
`@dag(...)`, и MUST строить замыкание локальных импортов под корнем
DAG (`dags.*` относительно корня, относительные импорты). Импорты
`airflow` / `plugins` / `shared` и сторонних пакетов MUST NOT
входить в замыкание. Соседний файл MUST учитываться только если DAG
(прямо или транзитивно) его импортирует.

`PROCESS` MUST называться по модулю файла с конструктором DAG
относительно корня. `EXTRACTION_SOURCE` MUST брать `description` из
`DAG(...)`, если он есть, и MUST иметь `EXTRACTS_TO` на `PROCESS`.

Режим сопоставления целей `WRITES_TO` MUST задаваться
`APP_DWH_AIRFLOW_LINEAGE_MODE`, CLI `--airflow-lineage-mode` или
полем `airflow_lineage_mode` в `POST /api/v1/collect`. Допустимые
значения:

```text
catalog
code
```

По умолчанию MUST быть `catalog`. Неизвестный режим MUST
отклоняться на границе конфигурации или HTTP.

В режиме `catalog` таблица MUST попадать в `WRITES_TO` только если она
уже есть в снимке каталога (уникальное совпадение schema+name или
уникальное имя) и в замыкании DAG есть свидетельство записи.
Отсутствие таблицы в снимке MUST пропускать этот DAG, а не создавать
узел.

В режиме `code` адаптер MUST материализовать цель из исходников DAG даже
если таблицы нет в снимке каталога: при уникальном совпадении MUST
использовать каталожный объект, иначе MUST создать unresolved `TABLE`.
Адаптер MUST NOT запрашивать сканируемый DWH, чтобы решить, существует
ли таблица.

Объекты, которые адаптер создаёт или обновляет, MUST получать атрибут
`source_files` — относительные пути файлов в корне DAG, из которых
объект разобран. Это MUST относиться к `PROCESS`, `EXTRACTION_SOURCE`,
unresolved `TABLE` и `STORAGE_LOCATION`.

В режиме `code` path-литералы в замыкании импортов MUST материализоваться
как `STORAGE_LOCATION` только если это landing/object-store путь
(`s3://`, `/data/...`, Windows-путь с landing/airflow_files), а не
веб-ресурс (`/Content/img/...`, `/static/...`, `.png`/`.css`/`.js` на
POSIX-пути). Такой `STORAGE_LOCATION` MUST порождаться из
`EXTRACTION_SOURCE` (`EXTRACTS_TO`) и MUST NOT быть корневым родителем
цепочки. `PROCESS` MAY иметь `READS_FROM` на эту локацию. Неимпортированный
соседний файл MUST NOT порождать `STORAGE_LOCATION`. Блок
`if __name__ == "__main__"` MUST игнорироваться целиком: пути, SQL и
прочие объекты внутри него MUST NOT попадать в каталог.
HTTP-константы MUST NOT становиться `DATA_SOURCE`.

В режиме `catalog` адаптер MUST NOT создавать `DATA_SOURCE` и MUST NOT
создавать `STORAGE_LOCATION`. Цепочка Airflow MUST быть:

```text
EXTRACTION_SOURCE -> PROCESS -> TABLE
```

В режиме `code` цепочка MAY включать storage:

```text
EXTRACTION_SOURCE -> STORAGE_LOCATION
EXTRACTION_SOURCE -> PROCESS -> TABLE
PROCESS -> STORAGE_LOCATION
```

В обоих режимах таблица MUST попадать в `WRITES_TO` только если в
замыкании DAG есть и идентичность таблицы, и свидетельство записи.
Идентичность MAY браться из:

- `__tablename__` / `__table_args__['schema']` SQLAlchemy-класса
  (в том числе из констант модуля);
- `DbModelAdapter(..., table, schema)`;
- аргументов `schema=` / `table=` / `tablename=` / `name=` у
  `insert_to_db`, `to_sql`, `CSVtoPostgresUpsert` и родственных вызовов;
- SQL `INSERT INTO` / `UPDATE` / `MERGE` `schema.table`.

Свидетельство записи MUST быть вызовом `INSERT`/`UPDATE` SQL,
`postgresql.insert` / `on_conflict_do_update`, `session.merge` /
`session.add`, `upsert` / `upsert_db` / `insert_to_db` /
`insert_values_to_db` / `to_sql` / `CSVtoPostgresUpsert` в том же
замыкании. Упоминание таблицы в `SELECT` или в модуле без записи
MUST NOT создавать `WRITES_TO`. HTTP-константы в `scrapers/` MUST NOT
становиться `DATA_SOURCE`.

Адаптер MUST NOT создавать `DATA_SOURCE`. В режиме `catalog` адаптер
MUST NOT создавать `STORAGE_LOCATION`.

Рёбра `VIEW` / `MATERIALIZED_VIEW` `DERIVED_FROM` таблицу MUST писать
адаптер `postgres_sql`. Вместе адаптеры MUST образовывать:

```text
EXTRACTION_SOURCE -> PROCESS -> TABLE -> VIEW
```

Несколько DAG на одну таблицу MUST сохраняться как несколько
процессов. Отсутствие корня исходников MUST быть пропуском адаптера,
не `FAILED`.

#### Scenario: Имя модуля DAG становится PROCESS

- GIVEN каталог содержит таблицу `raw.ice_brent`
- AND файл `load_platts_egd.py` содержит `DAG(dag_id="load_platts_egd",
  description="Загрузка Platts")` и запись в `raw.ice_brent`
- WHEN выполняется адаптер `airflow_dags`
- THEN создаётся `PROCESS` с именем `load_platts_egd`
- AND создаётся `EXTRACTION_SOURCE` с description «Загрузка Platts»
- AND есть ребро `EXTRACTS_TO` на процесс и `WRITES_TO` на таблицу
- AND `DATA_SOURCE` и `STORAGE_LOCATION` не создаются

#### Scenario: DAG импортирует scraper и модуль записи

- GIVEN DAG уровнем выше импортирует `scrapers.fetch.get_online_data`
  с HTTP-константой и отдельно `db_models` с `__tablename__` и
  `insert`/`upsert`
- WHEN выполняется адаптер `airflow_dags`
- THEN `PROCESS` — модуль DAG
- AND `WRITES_TO` указывает на таблицу из `db_models`
- AND HTTP из scraper не становится `DATA_SOURCE`

#### Scenario: SELECT без записи не создаёт lineage

- GIVEN DAG содержит `SELECT ... FROM raw.ice_brent` и не содержит
  команд записи
- WHEN выполняется адаптер
- THEN ребра `WRITES_TO` нет

#### Scenario: Режим catalog не создаёт таблицу вне снимка

- GIVEN режим `catalog`
- AND DAG пишет в `src_gassco.gassco_flows`
- AND этой таблицы нет в снимке каталога
- WHEN выполняется адаптер `airflow_dags`
- THEN `PROCESS` и `WRITES_TO` для этого DAG не создаются

#### Scenario: Режим code материализует unresolved цель

- GIVEN режим `code`
- AND DAG содержит `INSERT INTO src_gassco.gassco_flows`
- AND этой таблицы нет в снимке каталога
- WHEN выполняется адаптер `airflow_dags`
- THEN создаётся `PROCESS` и unresolved `TABLE`
- AND есть ребро `WRITES_TO` на эту цель
- AND у `PROCESS` и таблицы в `source_files` есть файл DAG

#### Scenario: Пути в DAG не становятся storage

- GIVEN DAG пишет в таблицу
- AND соседний неимпортируемый `paths.py` содержит
  `"/data/landing/platts/egd"`
- WHEN выполняется адаптер `airflow_dags`
- THEN `STORAGE_LOCATION` не создаётся
- AND цепочка остаётся `EXTRACTION_SOURCE -> PROCESS -> TABLE`

#### Scenario: Режим code ставит source_files на storage

- GIVEN режим `code`
- AND DAG импортирует `paths.py` с `LANDING = "/data/landing/platts/egd"`
- AND в замыкании есть запись в таблицу
- WHEN выполняется адаптер `airflow_dags`
- THEN создаётся `STORAGE_LOCATION` для этого пути
- AND `source_files` содержит `paths.py`
- AND `EXTRACTION_SOURCE` имеет `EXTRACTS_TO` на storage
- AND есть ребро `READS_FROM` от процесса

#### Scenario: Блок __main__ не порождает объекты

- GIVEN режим `code`
- AND после `if __name__ == "__main__"` есть `/data/landing/x` и `INSERT`
- AND вне блока есть запись в другую таблицу
- WHEN выполняется адаптер
- THEN объекты из `__main__` не создаются

#### Scenario: Веб-путь не становится STORAGE_LOCATION

- GIVEN режим `code`
- AND в DAG есть `"/Content/img/word.png"`
- WHEN выполняется адаптер
- THEN `STORAGE_LOCATION` для этого пути нет

#### Scenario: Корень DAG не задан

- GIVEN `airflow_dags` включён, но корень исходников пуст или отсутствует
- WHEN выполняется адаптер
- THEN прогон `SUCCESS` со `skipped`
- AND каталог и SQL lineage остаются доступны

### Requirement: HTTP-запуск снимочного сбора

`POST /api/v1/collect` MUST запускать ту же последовательность сборщиков,
что и CLI. Запрос MUST принимать:

```text
reset
airflow_lineage_mode
```

Флаги MUST приниматься как query-параметры и как JSON-тело. Если поле
задано в теле, оно MUST иметь приоритет над query. Опущенный
`airflow_lineage_mode` MUST брать значение из
`APP_DWH_AIRFLOW_LINEAGE_MODE`.

Опциональный список `schemas` MUST ограничивать чтение каталога
PostgreSQL (схемы, отношения, колонки, `pg_*_relation_size` и SQL
lineage view/matview) этими именами `pg_namespace`. Опущенный или пустой
список MUST означать все пользовательские схемы. Имя, которого нет среди
пользовательских схем, MUST завершать прогон каталога `FAILED` до
`mark_missing_as_deleted` и до запросов размера отношений.

Список MUST быть полным активным охватом этого прогона. Объекты
каталога `postgres` вне списка MUST soft-delete, как и при полном
сборе. Поэтому следующий прогон MUST повторять уже собранные схемы и
добавлять новые (`raw`, затем `raw,core`), а не заменять список одной
новой схемой.

Ответ MUST содержать применённые `reset`, `airflow_lineage_mode` и
`schemas` (`null`, если фильтр не задан), сводку прогонов по имени
коллектора и `failed`. HTTP-статус MUST быть
`200`, если ни один коллектор не `FAILED`, и `500`, если хотя бы один
прогон `FAILED`. Страницы UI MUST NOT вызывать этот метод.

#### Scenario: DAG запускает collect в режиме code

- GIVEN оператор вызывает `POST /api/v1/collect` с
  `airflow_lineage_mode=code` и `reset=true`
- WHEN сбор завершается без `FAILED`
- THEN ответ `200` содержит `airflow_lineage_mode=code` и `reset=true`
- AND снимки собраны в выбранном режиме

#### Scenario: Охват схем наращивается в одном запросе

- GIVEN предыдущий collect с `schemas=raw` записал объекты `raw`
- WHEN следующий collect вызывается с `schemas=raw,core`
- THEN объекты `raw` остаются активными
- AND объекты `core` добавляются
- AND запросы размера отношений не читают прочие пользовательские схемы

#### Scenario: Схема вне списка soft-delete

- GIVEN в Portal DB активны объекты схем `raw` и `core`
- WHEN collect вызывается с `schemas=core`
- THEN объекты `raw` помечаются удалёнными
- AND объекты `core` остаются активными

#### Scenario: Неизвестная схема не стирает снимок

- GIVEN в Portal DB есть активный каталог
- WHEN collect вызывается с именем схемы, которого нет в DWH
- THEN прогон каталога `FAILED` с сообщением, что схема не найдена
- AND предыдущие активные объекты не soft-delete

#### Scenario: Отказ коллектора виден DAG

- GIVEN хотя бы один коллектор завершился `FAILED`
- WHEN DAG вызывает `POST /api/v1/collect`
- THEN HTTP-статус `500`
- AND тело содержит сводку прогонов

### Requirement: Изменения структуры

После каталожного прогона система MUST сравнивать нормализованный
`structure_hash` и создавать события:

```text
ADDED
REMOVED
RENAMED
STRUCTURE_CHANGED
DESCRIPTION_CHANGED
```

Удалённый объект MUST soft-delete, чтобы история снимков оставалась
запрашиваемой. Native OID MAY использоваться как вспомогательный
признак rename внутри одного lifecycle базы и MUST NOT считаться
глобально стабильным.

#### Scenario: Добавлена колонка

- GIVEN вчерашняя таблица имела три колонки
- AND сегодняшний снимок содержит четвёртую колонку
- WHEN детектор изменений сравнивает hash
- THEN создаётся `STRUCTURE_CHANGED` с детальным diff колонок

### Requirement: Локализованные отказы и свежесть

Прогон MUST завершаться сводкой полноты, а не all-or-nothing.
`GET /api/v1/collection-status` MUST различать:

```text
SUCCESS
PARTIAL
FAILED
STALE
```

Частичный отказ loader metadata MUST NOT скрывать остальной каталог.

#### Scenario: S3 недоступен, каталог успешен

- GIVEN каталожный коллектор завершился успешно
- AND коллектор S3/file storage завершился с ошибкой
- WHEN клиент читает collection-status
- THEN статус хранения `FAILED` или `PARTIAL`
- AND каталог остаётся доступен для чтения
