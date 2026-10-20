# Design: python-modules-lineage

## Context

Lineage adapters already split sources:

```text
postgres_sql         → DERIVED_FROM (pg_depend)
extraction_registry  → registry chain + PROCESS from load_options
airflow_dags         → AST under APP_DWH_AIRFLOW_DAGS_ROOT
```

Python write targets were resolved by importing loader modules. That path
is removed for registry PROCESSes; AST under a dedicated root replaces it.

## Decisions

1. **Separate root** — `APP_DWH_PYTHON_MODULES_ROOT` is independent of
   `APP_DWH_AIRFLOW_DAGS_ROOT`. Same physical tree MAY be configured
   twice only by operator choice; adapters MUST NOT share the setting.

2. **Registry owns identity** — `python_modules` MUST NOT create a new
   `PROCESS`. It attaches `WRITES_TO` / optional `READS_FROM` to the
   existing `extraction_registry` PROCESS keyed by `attributes.module`.

3. **No execution** — scan with `ast` only; never `importlib` loader
   modules for lineage.

4. **Reuse write heuristics** — share `airflow_syntax` parse/closure/
   write-target helpers; entry point is dotted module name, not `DAG(`.

5. **Modes** — `APP_DWH_PYTHON_MODULES_LINEAGE_MODE=catalog|code`
   mirrors Airflow semantics for table matching.

6. **Deferral** — after registry ingest, Python PROCESS has
   `metadata_status=DEFERRED`, `lineage_status=UNRESOLVED` until
   `python_modules` resolves (or root is absent → stays deferred,
   diagnostic optional when module file missing under root).

7. **Default pipeline** — include `python_modules` in the built-in list;
   without root → `SUCCESS` + `skipped` (same pattern as Airflow).

## Risks / Trade-offs

- AST false positives/negatives same class as Airflow.
- PROCESS without module path cannot be resolved.
- Existing environments relying on `get_metadata()` lose automatic
  writes until the modules root is mounted.

## Verification

Registered:

```text
cd backend/core-service && PYTHONPATH=. .venv/bin/pytest tests/unit/test_catalog/ -v
```
