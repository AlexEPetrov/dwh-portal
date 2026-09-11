# Наполнение каталога снимками

## Purpose

Коллекторы периодически собирают операционные метаданные DWH, реестра
загрузки и логического хранения, сохраняют канонические снимки и
диагностику. Это позволяет порталу показывать каталог, размеры, lineage
и изменения без дорогих запросов в момент открытия страницы.

## Requirements

### Requirement: Снимочный сбор отдельно от чтения API

Коллекторы MUST выполняться вне пользовательского запроса. Нормальный
путь `UI -> Portal API -> Portal DB` MUST NOT запускать полное
сканирование DWH.

Коллектор каталога MUST читать PostgreSQL system catalog через
выделенное read-only соединение и MUST NOT выполнять `COUNT(*)` по
крупным таблицам только ради UI.

#### Scenario: Повторный запуск идемпотентен

- GIVEN объект уже есть в Portal DB с тем же каноническим identity
- WHEN коллектор запускается повторно
- THEN новый канонический `Asset` не создаётся только из-за смены
  отображаемого имени
- AND обновляются `last_seen_at` и связанные снимки

### Requirement: Канонические identity

Коллекторы MUST использовать устойчивые identity:

- база PostgreSQL: provider + connection identity + имя базы;
- схема: актив базы + имя схемы;
- таблица/представление: актив схемы + имя объекта;
- extraction source: `sys.data_extraction_sources.id`;
- data source: `sys.data_source_items.id`;
- process: id источника извлечения + стабильный ключ handler;
- storage location: нормализованный дескриптор расположения.

Секреты, credentials и host-specific детали MUST NOT сохраняться в
Portal DB.

#### Scenario: Storage options без секретов

- GIVEN `storage_options` содержит путь и credentials
- WHEN коллектор материализует `STORAGE_LOCATION`
- THEN в атрибутах остаётся логический `path` и шаблоны
- AND credentials отсутствуют

### Requirement: Source-to-DWH lineage из реестра извлечения

Первая цепочка lineage MUST восстанавливаться из
`sys.data_extraction_sources`:

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
