## Context

See `proposal.md` Why. Current collectors hard-wire
`ExtractionRegistryCollector` as the only lineage writer.
`LineageProvider` is extraction-registry-specific. PostgreSQL catalog
collection stores inventory and `CONTAINS`, but not view dependencies.
Airflow is not a metadata source.

Routing: `AGENTS.md`, `backend/core-service/AGENTS.md`,
`rules/README.md`, topics `catalog` and `ingestion`, workflow
`SPEC-WF-HIGH-RISK-SEMANTICS`. HTTP contract chain is not in scope
unless FastAPI authoring shape changes.

Authoring / published / generated: no OpenAPI regeneration required for
this change. Reading remains `GET /api/v1/assets/{id}/lineage`.

## Goals / Non-Goals

**Goals:**

- One `LineageAdapter` contract; built-in adapters plus `module:Class`.
- SQL view/table graph without extraction registry.
- Extraction registry optional (skip, not fail).
- Reverse Airflow reconstruction from local DAG sources as text.
- Existing extraction-registry tests keep passing when the registry is
  present.

**Non-Goals:**

- Executing or importing DAG Python.
- Cloning a git remote; only a configured local root.
- Column-level lineage, dbt, OpenMetadata adapters (future plugins).
- New HTTP endpoints or new relationship types.
- Frontend redesign; existing `READS_FROM`/`WRITES_TO`/`DERIVED_FROM`
  rendering is reused.

## Decisions

### 1. Adapters own collection runs, not a shared discovery DTO

Each adapter implements `collect(now) -> CollectionRun` and writes
canonical assets/relationships through `PortalStore`.

Alternative considered: a shared `DiscoveredEdge` bus. Rejected for
MVP — extraction registry already materializes a complex graph; wrapping
it is cheaper than a second model.

### 2. Built-in registry + dynamic import

Built-in names resolve in-process. Any other spec `module:Class` is
loaded with `importlib` and constructed as
`(store, settings, **kwargs)`.

Alternative considered: setuptools entry points. Rejected — closed-world
config via `APP_DWH_LINEAGE_ADAPTERS` is enough and does not invent a
packaging plugin scan.

Default list: `postgres_sql,extraction_registry`. `airflow_dags` is
appended when `APP_DWH_AIRFLOW_DAGS_ROOT` is set.

### 3. SQL dependencies from `pg_depend`/`pg_rewrite`

PostgreSQL rewrite dependencies are the durable source for
view → relation edges. Parsing `pg_get_viewdef` is a fallback we do not
take (fragile SQL).

Adapter source_provider for those edges is `postgres` so they merge with
catalog identities.

### 4. Missing extraction registry is SUCCESS skipped

`UndefinedTable` / empty `information_schema` for
`sys.data_extraction_sources` is `ExtractionRegistryMissing`. The
collector records `SUCCESS` + `details.skipped=true`. Unexpected
errors remain `FAILED` (existing runner test with `RuntimeError`).

### 5. Airflow edges reuse PROCESS READS_FROM / WRITES_TO

`PROCESS WRITES_TO TABLE` and `PROCESS READS_FROM DATA_SOURCE` match
the existing list/map UI (PROCESS in the middle). DAG code is never
executed; matching is token/literal scan as specified.

### 6. Human approval checkpoint

Intended semantics were given by the product request: adapter/plugin
architecture, SQL-only lineage without extraction sources, reverse
Airflow from DAG text. Remaining matching rules are fixed in the
ingestion delta spec rather than left open.

New semantic ambiguity (e.g. git clone, executing DAGs, new API shape)
re-opens the gate.

## Risks / Trade-offs

- [False-positive table names in DAG comments] → qualified names first;
  unqualified only if unique and not in the stop-list.
- [Multiple DAG files share helpers] → each file with a match becomes a
  PROCESS; diagnostics stay local.
- [pg_depend misses some dynamic SQL views] → unresolved/missing edges
  are acceptable; graph may be incomplete.
- [Dynamic `importlib` of `module:Class`] → trusted operator config
  only; same trust model as Python loader `get_metadata()` modules.

## Migration Plan

- Default config keeps extraction registry when the table exists.
- Deployments without the table start showing SQL lineage after the
  next collector run.
- Enable Airflow by setting `APP_DWH_AIRFLOW_DAGS_ROOT`.
- Rollback: omit new adapters via `APP_DWH_LINEAGE_ADAPTERS=extraction_registry`
  (loses SQL/Airflow edges on subsequent runs only if those adapters
  stop writing; existing edges remain until a future cleanup — adapters
  do not delete other adapters' edges).

## Verification IDs

- `CORE-PYTEST-TARGET` for `tests/unit/test_catalog`

`OPENAPI-EXPORT` / `FRONTEND-GEN-API` / `FRONTEND-BUILD` are not
required unless authoring API shape changes during implementation.

## Open Questions

None that affect specs or the task breakdown. Git-hosted DAG repos and
OpenMetadata remain future adapters.
