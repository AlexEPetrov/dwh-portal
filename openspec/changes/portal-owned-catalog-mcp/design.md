# Portal-owned MCP design

## Status

Architecture, Pydantic update, temporary anonymous read access and the task-scoped
missing-guide exception are approved. Source implementation and local checks are
complete; the proposal records evidence and unexecuted container checks.

The user subsequently approved the missing-guide exception for this task and
instructed implementation of temporary anonymous read-only mode. SDK dependency
reconciliation uses `mcp==2.3.0`, `pydantic==2.12.5`, `sse-starlette==3.0.2` and
`uvicorn==0.35.0`; the latter three versions are present in the SDK release's
upstream lockfile. The first dependency dry-run rejected Portal's old
`uvicorn==0.30.5` because the SDK requires `uvicorn>=0.31.1`. FastAPI and unrelated
direct dependencies remained unchanged and the repeated resolver check succeeded.

## Ownership and process model

Portal's Python process owns the MCP application and its startup/shutdown.
Mount the official Python SDK's Streamable HTTP ASGI interface on the existing
HTTP listener, before the frontend catch-all. Both supported Portal host entry
points must compose the same interface and lifecycle. No extra listener or
DSH-owned server process is introduced.

DSH connects through its existing official MCP client plugin. Another client
can connect to the same Portal interface without installing a DSH-specific
server or changing catalog semantics. No TypeScript server SDK is needed.

## Transport and access boundary

Use Streamable HTTP at `/mcp`, with stateless request handling where supported
by the pinned SDK. Protocol negotiation, request validation and transport
behavior belong to that SDK, not a handwritten JSON-RPC implementation.

Normal access uses a dedicated MCP-only Bearer token, validated before protocol
dispatch, including initialization and tool discovery. No default development
token, service-key fallback or browser-cookie fallback. Reject missing/invalid
credentials without echoing credentials in errors when anonymous reads are off.
Disabled MCP must not activate the SDK lifecycle or access the catalog.

The user explicitly approved a temporary exception: an operator setting may
enable anonymous reads, including initialization, discovery and the same exact
read-only catalog tools. It must not alter the tool allowlist or enable any
write operation. Keep this setting distinct from MCP enablement and token
configuration so removing the exception does not change the client protocol.
Document clearly that anonymous mode discloses catalog metadata to anyone who
can reach the endpoint. Host/Origin validation is still required but does not
authenticate clients or make anonymously served metadata private.

All accepted callers have the same read-only catalog scope. This is a
single-owner interface, not per-user authorization or OAuth discovery. Remote
clients require an explicitly approved TLS deployment; this task does not
configure remote access. Apply explicit trusted Host/Origin validation for the
MCP route without weakening existing REST behavior.

The MCP credential grants no access through the existing REST authentication
scheme. DSH resolves its dedicated credential from the owner's credentials
provider, never Portal session-signing, service, login or DB credentials.
Do not put credentials in URLs, command arguments, generated configuration
dumps or model-visible tool results. Client-side credential storage and plugin
configuration require the pinned DSH credential-redaction path to be verified.

## Tools

The server's exact allowlist:

- `search_catalog`: map explicit typed search/filter/page arguments to the
  existing catalog list service. Preserve total/page/freshness metadata and
  backend page-size bounds; do not fetch all pages automatically.
- `get_object`: return API-equivalent object detail and the complete ordered
  column list from existing catalog services. Missing objects are tool errors,
  not fabricated empty cards. Preserve nullable values and canonical fields.
- `get_lineage`: return the existing bounded graph, unresolved targets and
  collector freshness. Do not present bounded traversal as a complete graph.
- `get_object_links`: resolve an existing object ID to the existing UI object
  and lineage/Universe routes; do not open a browser or fetch arbitrary URLs. Prefer
  relative links unless an operator-configured, validated public Portal root
  is available. Never infer the public root from untrusted request headers.

Details mean the fields exposed by the existing Portal product API, not raw
provider credentials/options, database rows or arbitrary local file contents.

The approved external-chat follow-up adds typed `navigation.portal` and
`navigation.universe` to successful MCP envelopes without altering canonical
data. Object/column links target its card; lineage links target its graph;
Universe focuses the verified UUID. Search Portal links URL-encode existing
filters, restored by the Objects page using generated API queries. The search
Universe link is explicitly the unfiltered overview, not the filtered result.

Server/profile instructions request short conclusions and Markdown tables of
at most twenty rows, with Open in Portal below overflowing tables and explicit
Portal/Universe links for selected objects. This is not a backend data cap or
proof of model compliance. The pinned native `tool.call.toolview` client slot
supports per-tool components, but integration requires a separate browser bundle
and tests against the actual content/error/meta projection; raw structured MCP
values must not be assumed to reach that slot directly. Current work researches
that stage without implementing a native card or modifying DSH's transcript core.
Catalog descriptions and attributes are data, never instructions to execute.
Any output redaction must be documented and tested; do not silently diverge
from canonical catalog semantics or claim unredacted completeness.

## Canonical lineage and optional OpenLineage

Canonical nodes, edge types and endpoints remain unchanged. Existing traversal
is bounded and walks both endpoints; its output is not an execution log.
Known producer evidence stores SQL-derived views with `DERIVED_FROM` pointing
from dependent to source. A future flow-oriented projection must reverse
`DERIVED_FROM` and `READS_FROM` relative to their stored endpoints, while
preserving forward `EXTRACTS_TO`/`WRITES_TO` semantics. The demo seed appears to
contain inconsistent derived-edge direction and must not be silently rewritten
as part of this interface. Verify every mapping against current producers and
fixtures before enabling a projection. Do not invent run IDs, timestamps,
execution status, column lineage or job observations.

## Verification and reconciliation

Existing registered evidence:

- `PORTAL-HARNESS-STATE` and `PORTAL-HARNESS-DIFF` preserve/check working state.
- `CORE-PYTEST-TARGET` for the new MCP tests and relevant catalog tests;
  `CORE-PYTEST-UNIT` for regression coverage.
- `OPENAPI-EXPORT`, `FRONTEND-GEN-API`, frontend consumer classification and
  `FRONTEND-BUILD` when generated/consumer code changes.
- `PORTAL-HARNESS-SOURCE-TESTS`, `PORTAL-HARNESS-NODE-TESTS` and
  `PORTAL-HARNESS-SHELL-CHECK` for packaging/client changes, extending registered
  test invocations only after their evidence is authored.
- `OPENSPEC-VALIDATE-SPECS` after current-spec reconciliation.

Register any missing dependency inspection/resolution/install, MCP SDK protocol
integration and delta-validation commands before executing them. Tests must
cover unauthenticated discovery/calls, disabled MCP, wrong credentials,
Host/Origin rejection, exact tool discovery, canonical search/detail/column/
lineage equivalence, unknown tools, failure redaction, startup/shutdown and
unchanged REST authentication. Prove client compatibility against the pinned
SDK path rather than relying solely on source-text checks.

Container build/smoke remain user-run evidence because Docker is prohibited.
