---
id: SPEC-WF-PORTAL-HARNESS-IMAGE
status: active
authority: normative-workflow
applies_to:
  - infra/images/portal-harness/**
approval_policy: human_required
---

# Workflow: experimental Portal and harness image

## Purpose

Build an opt-in image containing the existing Portal backend and frontend plus
DeepSeek Harness (DSH). On 2026-11-19 the user explicitly approved replacing the
initial OpenCode packaging with DSH. This approval covers packaging and isolated
checks, not deployment changes, multi-user integration or new catalog semantics.

## Scope and safeguards

- Preserve the existing service image, build scripts, environment files and
  running deployments. Use a distinct experimental image tag.
- Retain the repository's RED SOFT Python builder and minimal runtime bases.
- Pin the harness version and verify the downloaded artifact before installing.
- The user selected source builds of the applications with prebuilt runtimes and
  third-party dependencies. Build DSH at commit
  `9c2670d3bce5275e0d1610272958121af87787bb` (tag `dsh-v0.2.2-rc.5`), with Node
  24.22.2 and upstream pnpm 11.28.5. Install with the frozen upstream lockfile,
  run its official build and use its runtime-closure deploy flags and exported
  staging validators. Do not substitute a published DSH installation or compile
  Python/Node themselves. No runtime `npx` downloads.
- Do not bake credentials, local environment files, session history, host
  dependencies or repository metadata into the image.
- Do not give the harness Portal database credentials. Disable general-purpose
  agent capabilities in the supplied profile; this is defense in depth, not an
  operating-system sandbox or multi-user security boundary.
- MCP tools, OpenLineage projection, shared authentication and browser control
  are outside this packaging iteration. Do not claim they are implemented.
- Do not install host tools, change Docker configuration, use elevated privileges,
  reset user changes or replace registered commands when execution fails.

## Registered procedure

Exact invocations are maintained in `rules/policy.yaml` and run from repository
root. Register concrete build and isolated smoke commands before running them.

1. Inspect working-tree paths with `PORTAL-HARNESS-STATE`; preserve unrelated work.
2. Inspect Docker access and the existing Python bases with
   `PORTAL-HARNESS-DOCKER-INSPECT`. Missing Docker or bases is `MISSING_EVIDENCE`;
   do not rebuild or pull replacements without resolving that scope.
3. Use `PORTAL-HARNESS-UPSTREAM-RESEARCH` to inspect the official DSH npm package
   metadata (registry.npmjs.org), release and matching repository sources. Verify
   Node requirements, persistent home, foreground Web launch, authentication and
   permission configuration. Fetch only upstream evidence; do not install on the
   host. Package/dependency installation is confined to the image build.
4. Add isolated image authoring sources under `infra/images/portal-harness/`.
   Build frontend from its existing workspace lockfile and preserve the backend's
   dependency and migration authoring sources.
5. Build the distinct experimental image and run registered isolated checks.
   Checks must not use production credentials, contact application databases or
   start the user's deployment. Remove only temporary containers owned by checks.
   The concrete commands are `PORTAL-HARNESS-BUILD` and `PORTAL-HARNESS-SMOKE`.
   `PORTAL-HARNESS-DEMO` is a separate user-run local trial with loopback-only
   ports and a dedicated harness volume; it is not automatic verification.
   Source-only checks are `PORTAL-HARNESS-SOURCE-TESTS`,
   `PORTAL-HARNESS-SHELL-CHECK` and `PORTAL-HARNESS-DIFF`.
6. Report actual artifact identity, checks executed and missing evidence. Image
   assembly alone does not prove model calls, MCP lineage or multi-user safety.

## Current execution restriction

Docker inspection was rejected by tool policy before any Docker command ran.
The user then explicitly requested source preparation and checks without Docker;
they will build the image and return its output. Do not execute Docker in this
task. Provide the registered build/smoke commands for the user and distinguish
local source checks from unexecuted container checks.

## Approved memory-startup correction

On 2026-11-20 the user reported the smoke container failing because startup
unconditionally validated PostgreSQL settings despite `APP_PORTAL_STORE=memory`.
They explicitly approved a backend startup correction and regression tests:
memory startup skips the SQL migration check; SQL startup and the standalone
migration CLI remain strict. Both `api.host` and `api.portal_host` must use the
same startup-only gate. Invalid store values must fail, not fall back to memory.
Do not disable migrations globally, add dummy DB credentials, alter migrations,
or bypass checks from the smoke harness.

Affected backend files also follow `backend/core-service/AGENTS.md` and the
API-contract workflow. Use `CORE-PYTEST-TARGET` with
`tests/unit/test_startup_migrations.py`, then `CORE-PYTEST-UNIT` and
`OPENAPI-EXPORT`; inspect the published contract for drift. Public paths/models
are unchanged, so consumer regeneration is required only if the export changes.
No Docker execution is authorized by this correction. The user reruns the image
build and smoke commands after the source checks.

The first targeted run passed 13 tests but exposed a second unconditional DB
dependency in `/health`. The user separately approved store-aware health on
2026-11-20: memory reports the database check as `skipped` without opening a
session; SQL retains its DB probe and HTTP 503 on failure. The explicit database
probe is unchanged in meaning. Include `tests/unit/test_health_store.py` in
targeted verification. Do not alter the smoke's assertions to hide a failing
required dependency.

Verification for this correction on 2026-11-20: the combined targeted startup and
health suite passed 19 tests; `CORE-PYTEST-UNIT` passed all 165 tests, with one
Starlette/AnyIO deprecation warning. `OPENAPI-EXPORT` succeeded and left the
published contract unchanged; no generated frontend client or consumer changed,
so frontend regeneration/build is not activated. Tests used local Python 3.12.3,
not the container's Python 3.13. No live database, migration or Docker commands
were executed. The corrected container smoke remains a user-run check.

## CLI argument-order correction

On 2026-11-20 the user-run smoke reported `unknown option '--patch'` after the
Portal startup correction. Pinned `apps/cli/src/args.ts` confirms that the first
unrecognized launcher argument starts verbatim application forwarding: launcher
flags must precede Web flags. Keep `--patch` before `--no-open` in the launcher.
The final image stage runs a shared-argv validator against the deployed pinned
CLI source parser and then Web help, with no Portal/DB/model execution. This
does not change DSH source pins or its compilation stage. The local packaging
suite passed 20 tests; Docker/native parser probes remain user-run checks.

The subsequent user build exposed Node's prohibition on automatic type stripping
inside `node_modules`. Load the pinned parser by explicitly reading its source,
calling Node's `stripTypeScriptTypes` API and importing temporary JavaScript
outside that directory, retaining its original Commander dependency. Do not
install a TypeScript compiler, mutate installed upstream files, or change the
DSH build stage. `PORTAL-HARNESS-NODE-INSPECT` and
`PORTAL-HARNESS-NODE-TESTS` permit a read-only host Node version check and
dependency-free loader fixtures. If Node/API support is absent, report missing
evidence rather than installing or switching runtimes. Docker remains prohibited.

Local evidence for the loader correction: Node 20.20.2, four loader fixtures
passed and one native stripping fixture skipped (API unavailable); all 20 Python
packaging tests passed. The final image stage runs those fixtures on Node 24
before the real pinned parser/Web-help checks. No DSH compilation inputs changed.

## Upstream comparison research

The user requested an Internet comparison of multi-user behavior in analogous
tools. `PORTAL-HARNESS-UPSTREAM-RESEARCH` permits read-only HTTPS requests to
official documentation and public GitHub repository/content/search APIs for
OpenCode, DeepSeek Harness, OpenHands, LibreChat and Open WebUI. Substitute an
explicit documentation/API URL for `url`; do not execute downloaded content or
install products. Distinguish community self-hosted, enterprise and cloud
features, browser login from catalog authorization, and history isolation from
execution isolation. Research does not authorize a change of product or deployment.
