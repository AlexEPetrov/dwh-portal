## MODIFIED Requirements

### Requirement: Загрузки EXTRACTION_SOURCE из реестра

For registry `EXTRACTION_SOURCE` assets,
`GET /api/v1/assets/{asset_id}/loads` MUST return a live server-paged read of
`sys.log_files`, filtered by the asset's `native_id` as `extraction_source_id`.
Loads MUST be ordered by load timestamp descending, with a descending identifier
tie-breaker when available. Files MUST NOT become lineage nodes or snapshots.

The endpoint MUST support `page`, `page_size`, and `include_total`. The latter
MUST default to `true` to preserve exact-count behavior for existing requests.
With `include_total=false`, the provider MUST NOT execute a count query, MUST
read at most `page_size + 1` rows, MUST return at most `page_size` items, and MUST
return `has_more` indicating whether an additional row exists. For an available
history whose count is omitted, `total` MUST be null rather than an invented
exact total. A known empty or unavailable history MAY return zero.

UI MUST initially request the newest 50 loads without an exact count. Older
pages MUST be fetched only on request; UI MUST NOT fetch all pages eagerly or
require the complete history count to display the first page.

Missing assets MUST return 404. Unsupported asset types/providers and missing
`sys.log_files` MUST return empty items with `available=false`, not 500. The
loads panel MUST remain available on registry source cards and Lineage pages.

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
