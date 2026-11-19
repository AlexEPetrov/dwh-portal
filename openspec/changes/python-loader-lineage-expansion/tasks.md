# Tasks

- [x] Resolve root/scoped routing, declared ingestion capability and approval.
- [x] Record proposal, design and ingestion delta.
- [x] Preserve safe entry point without changing process identity.
- [x] Implement bounded module-scoped, source-aware Python analysis.
- [x] Integrate TABLE targets, strict matching, evidence and diagnostics.
- [x] Add independent synthetic tests; leave shared Airflow implementation/tests unchanged.
- [x] Apply explicitly approved semicolon-root extension without changing setting name/type.
- [x] Normalize/deduplicate physical roots; diagnose invalid roots and continue usable roots.
- [x] Use ambiguity-safe lookup for entries, absolute imports and storage closure; anchor relative imports.
- [x] Add portable root-disambiguated provenance and isolate storage graphs/constants per process.
- [x] Add synthetic multi-root, alias/namespace import, collision, containment and storage regressions.
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

### Repeated verification after the approved multi-root extension

Both exact commands above were attempted again after implementing the extension
and its synthetic regressions. Each again exited 127 with
`/bin/sh: 1: .venv/bin/pytest: not found`. No tests executed. The status remains
MISSING_EVIDENCE for both CORE-PYTEST-TARGET and CORE-PYTEST-UNIT; this is not
passing evidence. No substitute executable or installation was attempted.

After the final blocked-import alias hardening, the narrower registered target
was also attempted:

```text
cd backend/core-service && PYTHONPATH=. .venv/bin/pytest tests/unit/test_catalog/test_python_loader_analysis.py -v
```

It also exited 127 with the same missing executable. All three extension
invocations are MISSING_EVIDENCE, not failed test assertions or passing tests.

Editor-provided OpenSpec diagnostics also reported errors in untouched changes
`add-dwh-portal-mvp`, `lineage-source-adapters` and `python-modules-lineage`.
Those unrelated artifacts were not edited or independently validated. The
reported missing-scenario issue in this change's MODIFIED delta was reconciled
by retaining every current scenario. No unregistered OpenSpec CLI was run.

## Actual scope and limitations

Modified authoring sources: registry collector, existing Python adapter, its
new private symbolic-analysis helper, catalog tests and ingestion OpenSpec.
User approval covers the implemented ingestion semantics. API workflow routing
was inspected: no HTTP authoring/shape changes, so no contract generation edges
were activated. No generated artifacts or Python/Rust shared contracts changed.
Sample sources, PostgreSQL lineage/view dependencies and frontend are untouched.

The approved extension additionally changes only the Python source-root setting
comment, Python adapter/analyzer, synthetic loader tests, this change's artifacts
and the current ingestion requirement. Setting name/type, PROCESS identity,
Airflow shared code, HTTP shape and generated/published contracts are unchanged.
Multiple-root evidence uses `root_N/relative/path.py`; one usable root keeps the
old relative filenames. Root order never breaks module ambiguity. Relative
imports use the owning (most specific) root, not a global fallback.

This is deliberately bounded static analysis, not a Python interpreter:
runtime-produced identities, unsupported dynamic constructs, ambiguous entry
points and exhausted budgets remain unresolved/diagnostic. Unknown branch
assignments merge conservatively; there is no arbitrary selection of one value.
Local helper source must be available to establish wrapper write behavior.
