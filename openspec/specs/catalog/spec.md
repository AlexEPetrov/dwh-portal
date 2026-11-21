# Каталог объектов DWH Portal

## Purpose

DWH Portal даёт аналитику и инженерам единый каталог объектов хранилища:
поиск таблиц и представлений, карточка объекта с описанием колонок,
оценкой размера, происхождением данных и историей структурных изменений.
Каталог читает нормализованные снимки Portal API и не выполняет
metadata-сканирование DWH при открытии страницы. Исключение: вкладка
«Загрузки» у `EXTRACTION_SOURCE` из реестра отдаёт постраничный live-журнал
`sys.log_files` через Portal API.

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

### Requirement: Корень lineage по умолчанию

`GET /api/v1/lineage/roots` MUST возвращать активные корневые объекты
lineage: все `DATA_SOURCE` и те `EXTRACTION_SOURCE`, у которых нет
родительского `DATA_SOURCE` по ребру `EXTRACTS_TO`.

Каждый узел корня MUST включать ограниченные счётчики достижимых
downstream-объектов (глубина обхода ограничена): `extraction_source_count`,
`process_count`, `table_count`, `view_count`. Рёбра в ответе корней
MUST оставаться пустыми.

Страница `/lineage` без выбранного объекта MUST показывать этот набор.
Выбор объекта MUST открывать его обычный ограниченный обход.

#### Scenario: Обзор корней на /lineage

- GIVEN есть `DATA_SOURCE` ICE, связанный с extraction source из реестра
- AND есть `EXTRACTION_SOURCE` из Airflow DAG без `DATA_SOURCE`
- WHEN клиент вызывает `GET /api/v1/lineage/roots`
- THEN в узлах есть ICE и Airflow extraction source
- AND extraction source из реестра отсутствует
- AND рёбер нет
- AND у ICE `extraction_source_count` ≥ 1

### Requirement: Обзор, хранение и изменения

`GET /api/v1/overview` MUST возвращать число объектов, итоги хранения,
сводку изменений и свежесть коллекторов.

`storage_by_schema` MUST содержать строку на каждую схему из снимков
хранения: `schema_name`, `total_bytes` и `description` активного объекта
`SCHEMA` с тем же именем. Если описания нет, `description` MUST быть пустым.

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

#### Scenario: Описание схемы в overview

- GIVEN активный объект `SCHEMA` `raw` с описанием
- AND у схемы есть снимок хранения
- WHEN клиент вызывает `GET /api/v1/overview`
- THEN в `storage_by_schema` у `raw` то же описание

### Requirement: Загрузки EXTRACTION_SOURCE из реестра

Для `EXTRACTION_SOURCE` с `source_provider=extraction_registry`
`GET /api/v1/assets/{asset_id}/loads` MUST возвращать постраничный список
фактически загруженных файлов из `sys.log_files` по `extraction_source_id`
(= `native_id` объекта), сортировка по времени загрузки DESC и по
идентификатору DESC при совпадении времени, если идентификатор доступен.

Это live-чтение журнала загрузок, не metadata-сканирование каталога и не
замена снимков. Overview, storage и список объектов по-прежнему из снимков.
Файлы MUST NOT становиться узлами lineage-графа.

Эндпоинт MUST поддерживать `page`, `page_size` и `include_total`.
`include_total` MUST по умолчанию быть `true`, сохраняя точное общее
количество для существующих запросов. При `include_total=false` провайдер
MUST NOT выполнять подсчёт общего количества и MUST читать не более
`page_size + 1` строк. Ответ MUST содержать не более `page_size` файлов и
`has_more`, показывающий наличие следующей страницы. Для доступного журнала
без подсчёта `total` MUST быть `null`, а не вымышленным точным количеством.
Для заведомо пустого или недоступного журнала MAY возвращаться ноль.

Если объекта нет — 404.
Для `EXTRACTION_SOURCE` из Airflow DAG, для других типов объектов и если
`sys.log_files` отсутствует, ответ MUST быть пустым списком с
`available=false`, а не 500.

UI MUST показывать вкладку «Загрузки» на карточке registry extraction source
и на странице Lineage при выборе такого объекта. UI MUST первоначально
запрашивать последние 50 загрузок без точного подсчёта. Старые страницы MUST
загружаться только по запросу пользователя; UI MUST NOT заранее загружать
всю историю или ждать её общего количества для отображения первой страницы.

#### Scenario: Страница загрузок постранично

- GIVEN extraction source из реестра с несколькими строками в `sys.log_files`
- WHEN клиент запрашивает `GET /api/v1/assets/{id}/loads?page=1&page_size=50`
- THEN ответ содержит не более 50 файлов, `total` и `available=true`
- AND строки отсортированы по времени загрузки по убыванию

#### Scenario: Airflow extraction source без журнала загрузок

- GIVEN `EXTRACTION_SOURCE` с `source_provider=airflow_dags`
- WHEN клиент запрашивает `/loads`
- THEN `items` пустой и `available=false`

#### Scenario: Existing exact-count caller

- GIVEN a registry extraction source with load history
- WHEN a client requests loads without `include_total`
- THEN `total` is the exact count and the page contains at most `page_size` items
- AND `has_more` indicates whether another page exists

#### Scenario: Latest 50 without counting history

- GIVEN a registry extraction source with more than 50 loads
- WHEN UI requests page 1 with `page_size=50` and `include_total=false`
- THEN the provider executes no count query and reads at most 51 matching rows
- AND the response contains the newest 50 items, `total=null`, and `has_more=true`
- AND older history is fetched only when the user requests another page

#### Scenario: Last or empty page

- GIVEN a count-free request at the end of load history
- WHEN no additional row exists after the requested page
- THEN `has_more=false`, with at most `page_size` items and `total=null`

#### Scenario: Unavailable history

- GIVEN an Airflow source, another asset type, or an unavailable log table
- WHEN a client requests loads
- THEN items are empty, `available=false`, and `has_more=false`

### Requirement: Браузер говорит только с Portal API

Веб-приложение MUST читать каталог, хранение, lineage, изменения и журнал
загрузок только через `/api/v1/*`. UI MUST NOT выполнять metadata-сканирование
DWH и MUST NOT вызывать `POST /api/v1/collect`. Операторский сбор запускает
Airflow или CLI.

#### Scenario: Страница объектов использует канонический список

- GIVEN пользователь открывает Objects
- WHEN страница загружает данные
- THEN она вызывает `GET /api/v1/assets` и отображает результат

### Requirement: Portal-owned read-only catalog MCP

Portal SHALL expose an opt-in Streamable HTTP MCP interface at `/mcp` on its
existing HTTP listener, owned by the Portal process and lifecycle. Clients such
as DSH and OpenCode SHALL NOT need to launch a Portal MCP server subprocess.
Ordinary Portal defaults SHALL keep MCP disabled. Existing REST/UI behavior
SHALL remain unchanged.

The exact tool surface SHALL be `search_catalog`, `get_object`, `get_lineage`
and `get_object_links`. Tools SHALL reuse existing catalog query orchestration
and DTO serializers, without HTTP loopback or DWH metadata scans. Search SHALL
preserve typed filters, page-size bounds, totals and collector freshness. Object
detail SHALL include API-exposed fields and the complete ordered column list.
Successful results SHALL contain `data` and `redacted_fields`; sensitive named
credential fields and raw extraction/load options SHALL be recursively masked
with explicit paths rather than silently omitted. These masks SHALL NOT be
represented as general detection of secrets in arbitrary prose.

Lineage SHALL preserve canonical node identities, stored relationship types and
endpoint directions, unresolved targets and freshness. It SHALL be labeled as
bounded static catalog evidence, not observed execution history. The interface
SHALL NOT invent OpenLineage runs/events, timestamps or column lineage.

Navigation tools SHALL verify object existence and return existing object,
lineage and object-focused Universe UI routes. Links SHALL be relative unless an operator-configured HTTP(S)
public origin without credentials/query/fragment is supplied. Request headers
SHALL NOT determine that public origin. Returning a link SHALL NOT open a browser.

#### Scenario: Replace the AI client

- **GIVEN** Portal is running with MCP explicitly enabled
- **WHEN** a compatible permitted client connects over Streamable HTTP
- **THEN** it discovers the same four read-only tools independently of DSH
- **AND** no extra MCP listener or client-owned server process is needed

#### Scenario: Search and inspect canonical metadata

- **GIVEN** an object and its columns exist in Portal snapshots
- **WHEN** a permitted MCP client searches and requests that object
- **THEN** search paging/freshness and object/column fields match the REST query contract
- **AND** credential-bearing named fields are masked with their paths disclosed
- **AND** no collection, SQL execution or DWH scan is initiated

#### Scenario: Preserve partial lineage and navigation

- **GIVEN** an object's bounded lineage includes unresolved targets
- **WHEN** a permitted MCP client requests its lineage and links
- **THEN** canonical graph endpoints and unresolved targets are preserved
- **AND** the result identifies bounded catalog evidence rather than execution history
- **AND** links use the verified Portal routes without opening a browser

### Requirement: Natural-language-first catalog capability discovery

The four existing MCP tools SHALL publish meaningful capability descriptions,
parameter descriptions and concrete structured output schemas. Successful
envelopes SHALL reuse canonical DTOs and preserve their JSON shapes after
credential-key masking. Output-validation failures SHALL be sanitized tool
errors, not successful null results. Canonical search paging/clamping and
read-only/security semantics SHALL remain unchanged.

Portal server instructions and the supplied catalog chat profile SHALL guide
the LLM to choose available capabilities for ordinary questions in the user's
language without requiring technical tool-name prompts or command syntax.
MCP SHALL expose typed capabilities, not interpret natural language inside
Portal. Guidance SHALL preserve identifiers, explain string-search limitations,
ask for clarification when multiple objects plausibly match a single-object
request, and prohibit arbitrary first-match selection or invented results.

The supplied DSH profile SHALL observe its actual tool registry and scope/step
admission through supported pinned APIs. Catalog registration readiness SHALL
require all four exact tool names, independently of process/guard readiness.
Scoped assembly evidence SHALL remain distinct from global registration and
unknown until observed. Neither SHALL be represented as proof of model tool
selection or successful reads. Missing/unknown capability guidance SHALL report
unavailability rather than invent resource URIs or execution fallbacks. Optional
MCP resource discovery SHALL remain disabled and the exact execution guard
SHALL NOT be broadened.

#### Scenario: Ask an ordinary multilingual question

- **GIVEN** a compatible tool-capable model and available catalog capabilities
- **WHEN** the user asks about an object in their own language without naming a tool
- **THEN** supplied guidance directs the model to choose calls from descriptions and schemas
- **AND** names/identifiers are preserved without claiming cross-language semantic search
- **AND** ambiguous single-object matches are presented for clarification, not arbitrarily selected

#### Scenario: Expose typed results without changing canonical reads

- **GIVEN** a client discovers and calls the four existing catalog tools
- **WHEN** successful results are serialized after recursive masking
- **THEN** advertised output schemas describe canonical search/detail/column/lineage/link data
- **AND** paging, freshness, graph endpoints and explicit redaction paths remain unchanged
- **AND** invalid outputs produce sanitized errors rather than successful null values

#### Scenario: A healthy guarded process has no catalog tools

- **GIVEN** DSH is running with its guard installed but MCP tools are absent or partial
- **WHEN** catalog readiness is checked or an agent assembles its context
- **THEN** actual registry/scope availability is reported separately from guard readiness
- **AND** missing, stale or unknown registration does not count as catalog readiness
- **AND** the model is instructed to report missing access without resources or execution fallbacks
- **AND** no readiness observation is claimed to prove model selection or a completed read

### Requirement: Compact external-chat answers and verified navigation

Successful MCP envelopes SHALL preserve canonical `data` and `redacted_fields`
and additionally expose typed `navigation.portal` and `navigation.universe` URLs.
Search Portal links SHALL encode the same query, database, schema, type, source,
status and changed-since filters and start at the first list page. Portal's
objects view SHALL restore those filters from URL state using existing generated
API calls and show removable active filter indicators. Object/column navigation
SHALL target the object card; dependency navigation SHALL target its lineage
view. Object Universe links SHALL focus the verified UUID. Search Universe links
SHALL be identified as the unfiltered source overview, not a filtered search.

Server and DSH profile guidance SHALL request a concise conclusion and compact
Markdown tables with at most 20 displayed data rows each. For more results,
guidance SHALL show the first 20 available rows, disclose shown/total or known
incompleteness, and place an explicit "Open in Portal" link below the table.
Selected-object responses SHALL offer explicit "Open in Portal" and "Open in
Universe" links in the user's language, using server-authored URLs. Guidance
SHALL NOT invent working buttons, browser actions, counts or completeness, fetch
all pages automatically, or omit freshness/unresolved/redaction disclosures.

This display rule SHALL NOT change canonical API/tool paging caps, graph bounds
or ordered column data. Model compliance SHALL remain separately verified by a
user-run chat; source fixtures SHALL NOT be claimed as a model roundtrip. Native
DSH tool cards SHALL remain a separate client extension, not implied by Markdown.

#### Scenario: More than twenty search results

- **GIVEN** a permitted search returns more than twenty matching objects
- **WHEN** an external catalog chat prepares its answer
- **THEN** guidance requests at most twenty rows and an Open in Portal link below the table
- **AND** that link restores the same supported filters in Portal without changing canonical results
- **AND** remaining pages are not automatically fetched solely to expand the answer

#### Scenario: Navigate an identified object and its dependencies

- **GIVEN** a verified object UUID and its bounded graph or columns
- **WHEN** a permitted client requests those results or object links
- **THEN** the response includes existing Portal and object-focused Universe routes
- **AND** the supplied guidance offers both explicit links without claiming a browser opened
- **AND** unknown objects still fail instead of producing navigation success

### Requirement: Explicit MCP read access mode

MCP SHALL have independent interface-enablement and anonymous-read settings.
When anonymous reads are off, every protocol operation, including initialization
and discovery, SHALL require a dedicated MCP-only Bearer credential. Ordinary
Portal service keys and browser cookies SHALL NOT be implicit fallback credentials.
MCP credentials SHALL NOT grant access through existing REST authentication.

As an explicitly approved temporary exception, an operator setting MAY enable
anonymous reads of the same exact catalog tool surface. Experimental combined-
image launchers MAY enable this exception by default; ordinary Portal defaults
SHALL keep it off. Operator guidance and startup warnings SHALL disclose that
anyone able to reach the endpoint can read catalog metadata in anonymous mode.
Changing access mode SHALL require a Portal restart.

Both access modes SHALL retain Host/Origin validation and a bounded request body.
Neither mode SHALL expose mutation, collection, SQL, shell, filesystem, arbitrary
URL fetching or live load-history tools. The interface SHALL NOT claim per-user
authorization, OAuth discovery, shared browser login or execution isolation.

#### Scenario: Reject unauthenticated discovery in token mode

- **GIVEN** MCP is enabled with anonymous reads off and a dedicated token configured
- **WHEN** initialization, discovery or a tool call lacks a valid Bearer credential
- **THEN** the request is rejected before catalog access
- **AND** supplied/configured credentials are not echoed in the response

#### Scenario: Temporary anonymous reads can be closed

- **GIVEN** MCP is enabled with anonymous reads explicitly permitted
- **WHEN** a client connects without a credential
- **THEN** discovery and the same four read-only catalog tools are available
- **AND** disabling anonymous reads and restarting restores the token requirement

#### Scenario: Disabled or unconfigured access fails closed

- **GIVEN** MCP is disabled, or protected MCP has no configured credential
- **WHEN** Portal starts or a client tries to access MCP
- **THEN** disabled MCP returns 404 without starting the SDK
- **AND** enabled protected MCP without a credential refuses startup
- **AND** no default development credential or fallback enables anonymous reads
