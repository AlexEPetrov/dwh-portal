# Tasks

- [x] Resolve root/scoped routing, declared ingestion capability and approval.
- [x] Record proposal, design and ingestion delta.
- [x] Preserve safe entry point without changing process identity.
- [x] Implement bounded module-scoped, source-aware Python analysis.
- [x] Integrate TABLE targets, strict matching, evidence and diagnostics.
- [x] Add independent synthetic tests; leave shared Airflow implementation/tests unchanged.
- [ ] Obtain successful CORE-PYTEST-TARGET evidence for tests/unit/test_catalog.
- [ ] Obtain successful CORE-PYTEST-UNIT evidence.
- [x] Reconcile current ingestion spec and record actual scope and blockers.

Reroute if scope expands. No API/Proto/generated reconciliation is activated.

## Actual verification (2026-11-19)

Both exact registered invocations were attempted from repository root:

```text
cd backend/core-service && PYTHONPATH=. .venv/bin/pytest tests/unit/test_catalog -v
cd backend/core-service && PYTHONPATH=. .venv/bin/pytest tests/unit/ -v
```

Both exited 127: `/bin/sh: 1: .venv/bin/pytest: not found`.
Classification: MISSING_EVIDENCE. No tests executed; no passing results claimed.
No installation, substitute interpreter, lint, or unregistered verification ran.
This change remains verification-blocked, not complete or ready to archive.

## Actual scope and limitations

Modified authoring sources: registry collector, existing Python adapter, its
new private symbolic-analysis helper, catalog tests and ingestion OpenSpec.
User approval covers the implemented ingestion semantics. API workflow routing
was inspected: no HTTP authoring/shape changes, so no contract generation edges
were activated. No generated artifacts or Python/Rust shared contracts changed.
Sample sources, PostgreSQL lineage/view dependencies and frontend are untouched.

This is deliberately bounded static analysis, not a Python interpreter:
runtime-produced identities, unsupported dynamic constructs, ambiguous entry
points and exhausted budgets remain unresolved/diagnostic. Unknown branch
assignments merge conservatively; there is no arbitrary selection of one value.
Local helper source must be available to establish wrapper write behavior.
