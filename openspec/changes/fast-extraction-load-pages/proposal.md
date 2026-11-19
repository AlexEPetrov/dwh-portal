# Fast extraction load pages

## Scope and approval

The user explicitly requested that an extraction source initially display only
the latest 50 loads, with older history available through paging or background
loading. Implement on-demand paging without an obligatory exact count. This is
an approved consumer-visible HTTP behavior change (`human_required`).

Preserve existing requests: `include_total` defaults to `true`. Clients opting
into `include_total=false` receive `total=null` and `has_more`; the provider
reads at most `page_size + 1` rows without a count query. No DWH schema,
credentials, deployment, or dependency installation changes are authorized.

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

## Current blockers

- Registered catalog pytest invocation failed: `.venv/bin/pytest` is missing.
- Registered OpenAPI export failed to import `fastapi`. The shell pipeline
  returned zero and printed `Done!`, but this is not successful publication.
- Published OpenAPI is unchanged. Do not generate a client from the stale
  contract or introduce a handwritten request workaround.
- The loads UI has not yet opted into the new mode. Its latency is not fixed
  until the registered publication/generation path becomes available.
- No production query plan or timing evidence has been collected; the count
  query is a confirmed blocking step, not a measured sole cause of latency.

## Verification recorded

- `CORE-PYTEST-TARGET` for `tests/unit/test_catalog`: attempted, exit 127;
  missing `.venv/bin/pytest` (`MISSING_EVIDENCE`).
- `OPENAPI-EXPORT`: attempted, `ModuleNotFoundError: No module named 'fastapi'`;
  publication failed despite pipeline exit 0 (`MISSING_EVIDENCE`).
- `FRONTEND-BUILD`: succeeded, exit 0, TypeScript and Vite build complete.
  Vite reported mixed static/dynamic imports and large-chunk warnings.
- Published OpenAPI diff: unchanged. Frontend generation was not run against
  this stale input. No live DWH performance measurements were executed.
