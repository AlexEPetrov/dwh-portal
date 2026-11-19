# Fast extraction load pages

## Scope and approval

The user explicitly requested that an extraction source initially display only
the latest 50 loads, with older history available through paging or background
loading. Implement on-demand paging without an obligatory exact count. This is
an approved consumer-visible HTTP behavior change (`human_required`).

Preserve existing requests: `include_total` defaults to `true`. Clients opting
into `include_total=false` receive `total=null` and `has_more`; the provider
reads at most `page_size + 1` rows without a count query. No DWH schema,
credentials, deployment, or dependency-version changes are authorized.
On 2026-11-19 the user additionally approved registering a local environment
preparation procedure, preserving the relocated existing environment by renaming
it, and installing the unchanged runtime/test manifests into a new local
Python 3.12.3 environment. This does not authorize system-package installation.

The long unresolved-target banner is a separate presentation-only change:
show the count and a collapsible full list without changing traversal or
discarding unresolved targets. Do not label every unresolved graph node as
loader metadata. The actual cause of the user's sandbox references remains
unverified without their runtime data.

## Contract and verification

Apply `rules/workflows/api-contract.md`: FastAPI authoring source, registered
catalog pytest, OpenAPI export, inspect published diff, generated frontend
client, frontend consumer, and frontend build. Generated artifacts are never
edited by hand. Reconcile the catalog delta through the OpenSpec sync lifecycle
when implementation and contract reconciliation are complete.

## Previous blockers (resolved on 2026-11-19)

- Registered catalog pytest invocation failed: `.venv/bin/pytest` is missing.
- Registered OpenAPI export failed to import `fastapi`. The shell pipeline
  returned zero and printed `Done!`, but this is not successful publication.
- Published OpenAPI is unchanged. Do not generate a client from the stale
  contract or introduce a handwritten request workaround.
- The loads UI has not yet opted into the new mode. Its latency is not fixed
  until the registered publication/generation path becomes available.
- No production query plan or timing evidence has been collected; the count
  query is a confirmed blocking step, not a measured sole cause of latency.

The environment was present but relocated: its pytest launcher's interpreter
path and activation script pointed to a former checkout. The earlier
`not found` output did not prove that pytest itself was absent. The old
environment is preserved at `backend/core-service/.venv.before-fast-load-pages/`
and excluded from Git. The new environment uses Python 3.12.3 and both unchanged
dependency manifests. The publication/generation blockers are now resolved.
Runtime timing remains unmeasured, not an implementation-completion blocker.

## Previous verification attempts

- `CORE-PYTEST-TARGET` for `tests/unit/test_catalog`: attempted, exit 127;
  missing `.venv/bin/pytest` (`MISSING_EVIDENCE`).
- `OPENAPI-EXPORT`: attempted, `ModuleNotFoundError: No module named 'fastapi'`;
  publication failed despite pipeline exit 0 (`MISSING_EVIDENCE`).
- `FRONTEND-BUILD`: succeeded, exit 0, TypeScript and Vite build complete.
  Vite reported mixed static/dynamic imports and large-chunk warnings.
- Published OpenAPI diff: unchanged. Frontend generation was not run against
  this stale input. No live DWH performance measurements were executed.

## Completion evidence — 2026-11-19

- `CORE-ENV-INSPECT`, `CORE-ENV-PRESERVE-RELOCATED`, `CORE-ENV-CREATE` and
  `CORE-ENV-INSTALL`: succeeded through the explicitly approved local-environment
  workflow; no package pins or system packages changed.
- Initial restored-environment catalog run: 140 passed, 1 failed. The failure
  exposed a server-log regression after multi-root support. Restored readable
  root formatting and missing-module log entries without changing traversal,
  stored diagnostics, or lineage semantics.
- `CORE-PYTEST-TARGET` for `tests/unit/test_catalog`: 141 passed, exit 0.
- `CORE-PYTEST-UNIT`: 146 passed, exit 0. Both runs reported one upstream
  Starlette/AnyIO deprecation warning.
- `OPENAPI-EXPORT`: succeeded and explicitly confirmed export. Published diff
  contains only `include_total` (default true), nullable `total`, and `has_more`.
- `FRONTEND-GEN-API`: succeeded from the updated contract. Generated types,
  service and schema files were regenerated, never edited by hand. Rerouting
  selected the existing API/frontend rules; no additional consumer scope arose.
- Consumer impact: affected. Catalog load queries now use the generated
  `includeTotal: false` option, including it in the query key. The shared panel
  starts at 50 rows, uses previous/next navigation, and does not invent a total
  or prefetch older pages. Asset changes still remount pagination and cancel
  obsolete requests through the existing query lifecycle.
- `FRONTEND-BUILD`: exit 0, TypeScript and Vite complete; existing mixed-import
  and large-chunk warnings remain. No frontend test script is registered; no
  browser automation or manual browser verification was executed.
- Compatibility: additive opt-in, preserving existing exact-count requests;
  null totals occur only for callers choosing the count-free mode.
- Catalog delta synchronized into `openspec/specs/catalog/spec.md`, preserving
  existing scenarios and Purpose. `OPENSPEC-VALIDATE-SPECS`: 2 passed, 0 failed.
- No deployment, database migrations, live DWH queries, query-plan inspection,
  or production latency measurements were performed. Do not claim a measured
  speedup or that a running deployment already uses this change.
