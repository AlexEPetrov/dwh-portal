## 1. Adapter contract

- [x] 1.1 Add `domains/catalog/lineage_adapters` with protocol, registry, and `module:Class` loading; verify unknown specs become a localized failed adapter rather than aborting the runner
- [x] 1.2 Add `APP_DWH_LINEAGE_ADAPTERS` and `APP_DWH_AIRFLOW_DAGS_ROOT` on `DwhCollectorSettings`; verify default list is `postgres_sql,extraction_registry` and Airflow is appended only when the root is set

## 2. Built-in adapters

- [x] 2.1 Make missing `sys.data_extraction_sources` a skipped SUCCESS in `extraction_registry`; verify `test_daily_runner_localizes_lineage_failure` still fails only on unexpected errors
- [x] 2.2 Add `postgres_sql` view/table `DERIVED_FROM` from `pg_depend`; verify a fake dependency becomes a lineage edge between catalog assets
- [x] 2.3 Add `airflow_dags` reverse reconstruction (DAG process, URL data source, no DAG execution); verify table-name and URL fixtures

## 3. Runner and specs

- [x] 3.1 Wire adapters into `run_daily_collection` after catalog/storage; verify one adapter failure does not hide catalog assets
- [x] 3.2 Update current `openspec/specs/catalog` and `openspec/specs/ingestion` to the approved adapter behavior
- [x] 3.3 `CORE-PYTEST-TARGET` for `tests/unit/test_catalog` via `cd backend/core-service && PYTHONPATH=. .venv/bin/pytest tests/unit/test_catalog -v`
