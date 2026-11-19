# Fast extraction load pages — implementation design

## Context

See `proposal.md` for the approved behavior and completion evidence. Catalog and
HTTP API topics select `rules/workflows/api-contract.md` and the HTTP contract
chain. Root, core-service and frontend routers apply. The user approved latest-50
on-demand paging and subsequently approved local environment preparation and
preservation of the relocated environment; no new business semantics are chosen.

## Goals / Non-Goals

Bound the response read and remove the obligatory count from the initial loads
request. Preserve exact-count behavior for callers that have not opted in.
Do not introduce schema/index migrations, cursor pagination, background full
history loading, another HTTP client, or a claim of measured production latency.

## Decisions

### Opt-in look-ahead instead of a mandatory count

The existing source filter and descending ordering remain. Count-free requests
fetch one extra row to determine `has_more`, then return only the requested page.
Use a nullable total rather than a fabricated count. Keeping exact counting as
the default preserves existing callers; globally removing it would change their
contract. Offset pagination is retained instead of adding a cursor contract.

### One shared count-free panel

The generated client option is consumed in catalog queries. The query key includes
the count mode to avoid sharing cached exact-count and count-free payloads. The
shared object-card/Lineage panel requests 50 rows, renders previous/next controls
from `has_more`, and never needs an exact total. Older pages are requested only
after navigation, not prefetched. Existing cancellation and no-placeholder query
behavior are preserved; the asset-keyed component resets the page on asset change.

### Reconcile the contract rather than bypass generation

Authoring source: `backend/core-service/src/api/portal/assets.py` and its response
models. Publication: `common/contracts/openapi/openapi.json`. Generated consumers:
`frontend/web/src/shared/api/generated/`. Handwritten consumers: catalog queries
and `ExtractionLoadsPanel.tsx`. Apply `OPENAPI-EXPORT`, inspect the diff, run
`FRONTEND-GEN-API`, reroute changed paths, and run `FRONTEND-BUILD`. A direct HTTP
workaround or hand-edited generated file is not an acceptable alternative.

### Preserve the relocated environment

The prior environment had absolute launcher/activation paths from another
checkout. Rather than patch generated launchers or delete user state, preserve
it under the explicitly approved backup name and create a new local environment.
Use the unchanged runtime and development manifests through
`rules/workflows/core-local-environment.md`. Registered preparation commands stop
on an existing target or backup. No package versions are changed to make checks
pass. A separate server-log-only regression found by the restored tests is fixed
without altering lineage resolution or stored data.

## Risks / Trade-offs

- A bounded result does not prove a bounded database scan or fast sort without
  a suitable index. No live query plans or timings were collected; avoid a
  numerical speedup claim.
- Offset paging over a changing live journal may shift page boundaries when new
  loads arrive. Existing live-read semantics remain; no snapshot/cursor promise
  is added.
- Frontend build and backend tests do not replace browser interaction evidence.
  No frontend test runner is registered; browser checks were not performed.
- The relocated backup consumes local disk space. Keep it excluded from Git and
  do not delete it as part of this task.

## Migration Plan

No data migration is required and no deployment was executed. A future rollout
must make the updated API available before the new frontend relies on its
count-free response. Existing consumers may continue requesting exact totals.
Reverting the frontend to its previous exact-count consumer behavior would not
require a database change; generated artifacts must still follow the registered
publication/generation pipeline if the API source changes.

## Verification

`CORE-PYTEST-TARGET` passes all 141 catalog tests; `CORE-PYTEST-UNIT` passes all
146 unit tests. `OPENAPI-EXPORT`, `FRONTEND-GEN-API`, `FRONTEND-BUILD`, and
`OPENSPEC-VALIDATE-SPECS` succeeded. See the proposal for warning details and
historical failures. The approved catalog delta has been synchronized while
retaining the original scenarios and Purpose.
