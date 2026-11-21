# Portal-owned catalog MCP interface

## Why

AI clients need the existing Portal catalog without owning its server lifecycle.
A stdio adapter launched by DSH couples connection setup to a particular client.
Portal should instead expose one read-only MCP interface reusable by DSH,
OpenCode and other compatible clients.

## Approval and gates

On 2026-11-20 the user approved replacing the DSH-owned stdio proposal with a
Portal-owned Streamable HTTP interface on the existing Portal HTTP listener.
The previous stdio implementation was never started.

Resolved approval policy: `human_required`. Architecture direction is approved.
The user subsequently approved updating Pydantic and explicitly requested a
temporary anonymous read-only MCP mode. Authentication design SHALL retain a
dedicated MCP-only Bearer token, separate from service keys/browser sessions,
but an explicit anonymous-read setting may bypass the credential check for the
same exact read-only tool surface. This is an approved temporary disclosure of
catalog metadata to anyone who can reach the MCP endpoint, not per-user access
control. No mutation capabilities are authorized by that exception.

Dependency compatibility is resolved locally: `mcp==2.3.0`,
`pydantic==2.12.5`, `uvicorn==0.35.0` and `sse-starlette==3.0.2` install together
with unchanged FastAPI and unrelated direct pins. The initial resolver failure
on old Uvicorn and subsequent successful reconciliation are recorded in design.

The architecture style guide referenced by `backend/core-service/AGENTS.md`
at `docs/design/adr/active/platform/core-service-architecture-style-guide.md`
is missing. The user explicitly approved a task-scoped exception: apply the
remaining root/core-service conventions for this implementation only.

Source implementation and local verification are complete. Container build,
native ABI, pinned DSH plugin activation and the extended offline container smoke
remain user-run evidence; do not present these as executed or proven.

## What changes

- Add a Streamable HTTP MCP interface owned by Portal
  at `/mcp`, on its existing listener and with Portal-managed lifespan.
- Expose only catalog search, full API-equivalent object details, ordered
  columns, bounded canonical lineage and verified browser links.
- Reuse catalog services and canonical serializers; do not call Portal's REST
  endpoints over loopback or duplicate catalog business semantics.
- Configure DSH as an ordinary MCP HTTP client. Do not launch an MCP child
  process from DSH, add a Node server SDK or give DSH database credentials.
- Retain exact DSH model-tool denial for all tools except the approved catalog
  allowlist. This is defense in depth, not the server authorization boundary.
- Preserve all existing REST behavior and Portal login behavior.

OpenLineage projection is optional follow-up, not a replacement for canonical
objects/relationships. Do not synthesize execution events or silently repair
existing relationship directions. No collection, SQL execution, loads-history
access, arbitrary URLs, filesystem access, shell, mutation tools or browser
automation are included.

## Capabilities

Modified capability: `catalog`, declared in `openspec/capabilities.yaml`.
The delta adds an AI-facing read interface; existing catalog requirements remain.

## Scopes, workflows and contracts

Expected authoring scopes:

- `backend/core-service/src/api/**`, catalog query/presentation orchestration
  only where needed, settings, dependency manifests and unit tests.
- `infra/images/portal-harness/**` for client configuration, environment
  filtering, packaging checks, user-run smoke and instructions.
- `rules/policy.yaml` and `rules/workflows/portal-harness-image.md` for approved
  execution evidence and replacement of the superseded stdio plan.
- This OpenSpec change and, after successful reconciliation, the current
  `openspec/specs/catalog/spec.md`.

Apply root/core-service routing, the API-contract workflow and the experimental
image workflow. HTTP authoring-source changes activate OpenAPI export; the
public interface addition also requires frontend API generation and consumer
impact classification under the existing workflow, even if the mounted MCP
transport does not add REST operations to OpenAPI. Do not hand-edit generated
contracts or generated clients. Run the frontend build if generated/consumer
files change. Any required workflow clarification must be explicit, not a bypass.

## Execution limits

No Docker commands, live SQL connections, migrations, collection or deployment
execution. Preserve user changes and environment files. Host dependency
installation follows the task-scoped dependency-resolution/reconciliation
procedure recorded in the image workflow. Read-only upstream research
has used the existing registered procedure only.

## Verification and reconciliation evidence

On 2026-11-20, Python 3.12.3:

- `CORE-MCP-DEPENDENCY-RESOLVE`, `CORE-ENV-INSTALL` and
  `CORE-MCP-DEPENDENCY-CHECK` succeeded after the documented Uvicorn correction.
- `CORE-PYTEST-TARGET`: all 31 MCP tests passed, including both Portal hosts,
  real SDK HTTP negotiation via in-process ASGI in anonymous/token modes,
  security controls, exact tool discovery, canonical equivalence and redactions.
- `CORE-PYTEST-UNIT`: all 196 tests passed. Two Starlette deprecation warnings
  concern `python_multipart` imports and the AnyIO blocking-portal alias.
- `OPENAPI-EXPORT` succeeded. Pydantic's compatible schema serialization drift
  makes dictionary `additionalProperties: true` explicit and expresses the same
  status enum reference without an `allOf` wrapper/title. No REST operations or
  runtime semantics were added/removed by that drift.
- `FRONTEND-GEN-API` succeeded; only generated schema declarations changed.
  Consumer impact: none; generated functions/types and handwritten UI unchanged.
  `FRONTEND-BUILD` succeeded, with mixed static/dynamic import and large-chunk warnings.
- `PORTAL-HARNESS-SOURCE-TESTS`: all 22 packaging tests passed.
- `PORTAL-HARNESS-NODE-TESTS`: six passed, one native-stripping test skipped
  because the host lacks the Node 24 stripping API. Exact tool-guard tests passed.
- `PORTAL-HARNESS-SHELL-CHECK` and `PORTAL-HARNESS-DIFF` passed.
- The catalog delta was reconciled into the current catalog spec;
  `OPENSPEC-VALIDATE-SPECS` passed both current specs.

Authoring sources: Portal MCP/settings, host lifespan wiring, dependency manifest,
tests, opt-in image client/guard/launcher/smoke and documentation/governance.
Published/generated artifacts: exported OpenAPI and generated frontend schemas,
changed only through registered pipelines. No database migration or env file
was changed. Existing deployments were not executed or modified.

Remaining evidence: user-run container build/smoke, UBI8/Python 3.13/native ABI,
actual pinned DSH plugin activation and model roundtrip, and owner provisioning
of protected DSH credentials. OpenLineage projection is explicitly deferred;
canonical lineage remains primary and existing seed direction drift is unchanged.

### User-run smoke follow-up: host-scope guard

The user reported healthy Portal startup followed by the supervisor's guard
initialization timeout. Inspection of pinned DSH `packages/core/tools/src/index.ts`
confirmed that `tools.restrict()` throws outside an agent scope. The host-scoped
image plugin incorrectly invoked it before registering its monotonic guard and
writing the marker. Remove that invalid call while retaining the exact global
execution policy, marker ordering, timeout and fail-closed supervision. No
backend, dependency or generated-contract semantics changed in this correction.

New activation/failure-ordering fixtures pass: nine Node tests passed, with one
native-stripping test skipped; all 22 packaging tests passed. These host fixtures
do not prove full pinned DSH startup. User-run container smoke and model tool
roundtrip remain outstanding, and the earlier completion evidence is local only.

### Approved infrastructure layout follow-up

On 2026-11-21 the user approved retaining image build/runtime sources under
`infra/images/portal-harness/`, moving the SQL Compose definition to
`infra/compose/docker-compose-portal-harness.json`, and moving launchers/example
settings to `infra/environments/portal-harness/`. File moves preserve user state
and executable modes. Launcher paths, registered invocations, tests and guides
were reconciled without changing service/project names, networks, volumes,
provider/MCP defaults, backend semantics or generated contracts.

All 29 Python packaging tests and 12 Node fixtures passed after relocation;
one native-stripping fixture was skipped on the host. Shell checks passed. Tests
use fake Docker argument capture only; actual deployment and container evidence
remain outstanding. The canonical procedure is the image workflow's layout section.
