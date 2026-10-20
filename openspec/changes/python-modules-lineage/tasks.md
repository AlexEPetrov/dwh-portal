# Tasks: python-modules-lineage

- [x] 1. OpenSpec proposal/design/delta for ingestion
- [x] 2. Add `APP_DWH_PYTHON_MODULES_ROOT` and
      `APP_DWH_PYTHON_MODULES_LINEAGE_MODE` on `DwhCollectorSettings`
- [x] 3. Stop Python `get_metadata` / import in
      `extraction_registry` (DEFERRED status)
- [x] 4. Implement `python_modules` adapter; register in built-ins
- [x] 5. Unit tests: deferral, skip without root, AST WRITES_TO
- [x] 6. Apply delta into `openspec/specs/ingestion/spec.md`
- [x] 7. Run registered pytest for catalog unit tests
