## ADDED Requirements

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

## MODIFIED Requirements

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
