---
id: SPEC-WF-PORTAL-HARNESS-IMAGE
status: active
authority: normative-workflow
applies_to:
  - infra/images/portal/**
  - backend/core-service/Dockerfile
  - backend/core-service/build_image.sh
  - infra/scripts/build_release.py
  - infra/scripts/package_release.py
  - infra/environments/test/README.md
  - infra/images/portal-harness/**
  - infra/compose/docker-compose-portal-harness.yml
  - infra/compose/docker-compose-checkout.yml
  - infra/environments/portal-harness/**
  - infra/environments/test/up.sh
  - infra/environments/test/down.sh
  - infra/environments/test/compose.sh
  - infra/scripts/build_env_portal_harness.sh
  - infra/scripts/package_portal_harness_release.py
  - infra/scripts/run_portal_harness_demo.sh
  - infra/scripts/build_env_test.sh
  - infra/scripts/_build_target.sh
  - infra/scripts/tests/**
  - infra/scripts/README.md
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
- The initial packaging iteration excluded MCP tools, OpenLineage projection,
  shared authentication and browser control. The explicitly approved HTTP MCP
  follow-up below supersedes only the MCP exclusion; the other exclusions remain.
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

## Approved combined-image SQL launch and MCP follow-up

On 2026-11-20 the user approved first connecting the combined image to the
existing working SQL Portal configuration, then read-only MCP for search,
details, OpenLineage and browser links. SQL support is not being reimplemented.
Prepare a separate Compose project using the existing environment file and
external `dwh_portal` network, without changing existing deployments or env files.
Memory remains for tests. Do not execute the SQL launch, connect to live databases,
apply migrations, collect data, print resolved Compose secrets or run Docker.
`PORTAL-HARNESS-SQL` is a user-run command with an explicit existing `env_file`.
MCP needs a separately documented contract, accurate OpenLineage mapping and
explicit authentication boundaries before semantic implementation; generic
service keys are not automatically read-only or per-user credentials.

### Portal-owned HTTP MCP supersedes the stdio proposal

On 2026-11-20 the user explicitly approved Portal-owned Streamable HTTP MCP
instead of a server child process launched by DSH. The Python SDK runs inside
Portal on its existing listener; DSH is a replaceable HTTP MCP client. Apply
core-service routing and the API-contract reconciliation workflow. The user
approved updating Pydantic and a task-scoped exception to the missing architecture
guide referenced by the core-service router: use the remaining root/core-service
conventions for this task only. Do not invent a replacement authority document.

The user also approved temporary anonymous read-only MCP access. Keep interface
enablement and anonymous-read mode separate. Anonymous access exposes catalog
metadata to anyone able to reach the endpoint; it is not authentication. Retain
a dedicated MCP-only Bearer-token mode so the exception can be switched off.
Neither mode may expose mutation, collection, SQL, shell, file or arbitrary URL
tools. Do not reuse general service keys or browser cookies as fallback.

The SDK requires updated runtime dependencies. Preserve the existing local
environment (its configuration identifies this checkout and Python 3.12.3).
`CORE-MCP-DEPENDENCY-RESOLVE` checks the approved manifest changes before
`CORE-ENV-INSTALL` updates runtime/test dependencies in that environment;
`CORE-MCP-DEPENDENCY-CHECK` checks the result. This is task-scoped dependency
reconciliation for the approved implementation, not permission to install host
tools, change indexes, upgrade unrelated packages or recreate the environment.
If resolution fails, report missing evidence instead of substituting an SDK.

Use `CORE-PYTEST-TARGET` for `tests/unit/test_catalog/test_mcp.py`, relevant catalog
tests and startup tests, then `CORE-PYTEST-UNIT`. Export OpenAPI and regenerate
the frontend API under the existing workflow, even if the mounted transport
does not publish REST operations. Classify the generated diff and consumer
impact; build frontend if generated/consumer files change. Docker, live SQL,
migrations and deployment execution remain prohibited.

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

## Host-scope guard activation correction

The user's 2026-11-20 container smoke reached healthy Portal startup but the
supervisor stopped the image because the DSH guard did not initialize. Pinned
`packages/core/tools/src/index.ts` rejects `tools.restrict()` without an agent
scope, and also rejects allowlists naming undiscovered global tools. The image
guard is a host-scoped plugin; its initial `restrict()` therefore throws before
the monotonic guard and readiness marker can be installed.

Remove the unsupported host-scope restriction, not the global execution guard.
Preserve the exact four catalog-tool allowlist, guard-before-marker ordering,
PID marker, timeout and fail-closed supervision. This is a correction of the
approved execution policy, not authorization to permit additional tools or to
claim model tool schemas are hidden. Add activation fixtures with host-scope
restriction rejection, no discovered MCP tools, registration failure and marker
failure, without writing the real marker in host tests.

Run `PORTAL-HARNESS-NODE-TESTS`, `PORTAL-HARNESS-SOURCE-TESTS`,
`PORTAL-HARNESS-SHELL-CHECK` and `PORTAL-HARNESS-DIFF`. No backend, SDK dependency,
DSH compilation inputs or public contract changes are needed. Docker execution
remains prohibited; the user rebuilds and reruns the registered container smoke.

Local evidence: all 22 Python packaging tests and nine Node fixtures passed;
one native-stripping fixture was skipped because the host lacks that API. Shell
syntax checks passed. These fixtures exercise plugin activation with mocked
marker I/O, not real pinned DSH startup; the repeated container smoke remains
outstanding. Existing backend/generated-contract changes are not altered by this
guard-only correction.

## Configurable internal Ollama provider profile

On 2026-11-21 the user reported DSH's built-in DeepSeek provider querying the
public `/models` endpoint despite the intended isolated runtime. The user
explicitly selected internal Ollama and requested launch/configuration parameters
for provider selection, with the internal endpoint and model supplied manually.
Provider model catalogs are lists of LLM model IDs/capabilities; they are unrelated
to Portal's data catalog and collector refreshes.

The approved runtime interface is `DSH_PROVIDER_MODE=ollama|upstream`, defaulting
to `ollama`. In Ollama mode, disable the built-in DeepSeek API-key/account adapters,
their account UI, DeepSeek web-provider plugins, the generic persisted pi-ai
adapter and the public default model. Compose a separately named pi-ai adapter
and default-model entry, using `DSH_OLLAMA_BASE_URL` (explicit OpenAI-compatible
`/v1` URL), `DSH_OLLAMA_MODEL` and configurable context/output limits. No endpoint
or model is inferred; both unset means UI/MCP only. Partial or invalid settings
fail before starting child processes. Configuration contains a credential
reference, not an internal gateway key. Do not forward cloud provider environment
credentials in Ollama mode or erase existing DSH credentials/session state.

Pinned upstream evidence: `packages/bundle/base/cordis.patch.yml` owns the enabled
DeepSeek provider/default model; `packages/llm/llm-pi-ai/{README.md,src/index.ts,
src/config.ts}` support explicit hand-declared profiles, local installed catalogs
and per-entry settings namespace IDs; `packages/core/agent-default-model/src/index.ts`
owns the configured default selection. The generic authorization service remains
available; it is not itself a public inference provider. Owner-driven UI changes,
saved session model choices and new endpoint configuration are trusted operator
actions, not confined by a profile. An actual isolated deployment must separately
deny external egress while allowing approved Portal DB/Ollama destinations.

Apply only image-source, configuration, documentation and fixture changes. Do not
alter backend MCP semantics, deployed networks, model installations, DSH source
pins or build stages. Runtime isolation is distinct from an offline build; image
assembly still uses the existing approved build-time dependencies/network path.
Run `PORTAL-HARNESS-SOURCE-TESTS`, `PORTAL-HARNESS-NODE-TESTS`,
`PORTAL-HARNESS-SHELL-CHECK` and `PORTAL-HARNESS-DIFF`. The existing registered
upstream-research command permits read-only pinned DSH evidence, not model calls.
Docker and calls to the user's Ollama remain prohibited for the agent.

Local source evidence on 2026-11-21: all 26 packaging tests and 12 Node fixtures
passed; one native-stripping fixture was skipped on the host. Shell checks
passed. These tests cover launch validation, secret filtering, default empty
Ollama routes, explicit upstream opt-in and patch-expression decisions. They do
not prove pinned DSH activation, actual Ollama compatibility or network-egress
isolation; the user-run container build/smoke and model roundtrip remain required.

## Approved build/composition/environment separation

On 2026-11-21 the user explicitly approved applying the repository's existing
three-layer layout to the experimental harness immediately:

- Keep image authoring/runtime sources, image build and isolated image smoke in
  `infra/images/portal-harness/`.
- Move the SQL Compose definition to
  `infra/compose/docker-compose-portal-harness.json`.
- Move `run-sql.sh`, `run-demo.sh` and the public `sql.env.example` into
  `infra/environments/portal-harness/`, with environment-specific guidance.

This is a behavior-preserving layout correction. Keep service/project names,
network/volume identities, loopback ports and provider/MCP defaults unchanged.
The memory demo remains its existing Docker-run wrapper; do not silently replace
its lifecycle with a different Compose project. Existing environment directories,
real env files and deployments are not modified. Preserve the user's executable
mode change on the SQL launcher and all source contents during the move.

`PORTAL-HARNESS-LAYOUT-MOVE` performs guarded non-overwriting filesystem renames
before path reconciliation. It is a one-time task action, not a deployment step.
Update launcher-relative Compose lookup, source tests, documentation and canonical
registered user-run/shell-check commands. Do not leave a second editable copy of
the same deployment definition under image sources. Add dependency-free tests
that invoke the relocated SQL launcher with a fake Docker executable to inspect
arguments only, including from an unrelated working directory. Tests must never
run Docker, resolve real Compose credentials or connect to databases/Ollama.

Run `PORTAL-HARNESS-SOURCE-TESTS`, `PORTAL-HARNESS-NODE-TESTS`,
`PORTAL-HARNESS-SHELL-CHECK` and `PORTAL-HARNESS-DIFF`. No backend, generated
contract, DSH compilation or actual deployment changes are activated by relocation.

Relocation evidence on 2026-11-21: all 29 source tests passed, including fake-Docker
argument capture from an unrelated cwd and rejection of a missing env file.
All 12 Node fixtures passed with one native-stripping skip; shell checks passed.
No real Docker executable, database, model endpoint or existing env file was used.

## Approved standalone network and host/internal-server database access

On 2026-11-21 the user reported that the old external `dwh_portal` network did
not exist. They explicitly selected PostgreSQL running on the Docker host now,
and requested configuration-only migration to another internal server later.
This supersedes the initial external-network assumption for the harness SQL
launch, not the preserved networks of existing deployments.

Use a Compose-owned, project-scoped bridge without `external` or a fixed shared
network name. Retain the existing `host.docker.internal:host-gateway` alias and
set only the public example's DB host to `host.docker.internal`, preserving the
user's database name, provider/model choices and other working-tree changes.
For a future internal DB server, the operator changes the same DB host/port/
credential environment settings; the image and bridge definition do not change.
Document listener, `pg_hba.conf`, firewall and routing requirements without
guessing a subnet or modifying the server/firewall. Never create an empty shared
network merely to suppress the error or use host networking as a silent fallback.

Do not execute Docker, access live SQL/Ollama, apply migrations or modify the
old deployment. This is an approved deployment-source correction only. Update
source regression coverage and operator guidance; run the registered source,
Node, shell and diff checks. No backend/public API authoring-source or generated
contract changes are required for this network adjustment.

Local evidence: all 30 Python packaging tests and 12 Node fixtures passed, with
one host native-stripping skip. Shell checks passed. Regression coverage asserts
the project-owned bridge, absence of external/fixed network names, retained host
gateway mapping and the example's host-gateway DB setting. Docker network
creation and actual PostgreSQL/Ollama connectivity remain user-run evidence.

## Approved minimal catalog agent composition

On 2026-11-21 the user reported `agent-preset/invalid` while creating a new DSH
session: the standard preset's `tool-plugin-manager` was waiting for the disabled
host `pluginManager`. They explicitly approved keeping only the needed catalog
capabilities. This is a preset-composition correction, not permission to enable
plugin installation, general coding tools or a public model provider.

Pinned `packages/bundle/web-app/presets/standard.patch.yml` declares its own child
tool rows; disabling a top-level host row does not modify those nested entries.
Replace the complete standard preset config with `catalog-preset.json`, retaining
the `standard` ID for already-recorded standard sessions but labeling it Portal
catalog. Keep only persona, agent instructions, time context and the existing
scoped compaction/result-pruning support. Catalog tools are inherited from the
host MCP client; the global exact-name execution guard remains unchanged.
Disable the other built-in coding presets and select the safe standard default,
including the registry's documented `selectedDefault` volatile field. Do not
erase session history, credentials or volumes. Sessions using a now-disabled
nonstandard preset may require a new catalog chat; do not silently rewrite logs.

Pinned evidence: the standard/minimal/cordis preset declarations, agent-preset
declaration schema and agent-preset-registry source/README. The preset JSON is
authoring input copied into the runtime stage before the existing DSH config
dump. Add source assertions for the exact safe composition, absent dangerous
tool rows and preserved disabled plugin manager. Run the registered source,
Node, shell and diff checks; the existing runtime image config validation and
user-run chat creation remain required evidence. DSH compilation inputs and
backend/API contracts do not change.

The user's separate report that Portal is unavailable at host loopback 5053 is
not diagnosed by this preset error. The API launcher binds all container IPv4
interfaces, and the supplied Compose publishes loopback 5053 to container 5051.
`health: starting` is not readiness evidence. Do not broaden published interfaces,
disable SQL startup checks or guess DB/server changes without actual Portal
startup/error evidence. Docker/live SQL execution remains prohibited for the agent.

## Approved portable lifecycle scripts and release artifact directory

On 2026-11-21 the user requested a down command, portable up/down behavior both
in checkout and copied release directories, preservation of the existing root
`.build/test` artifact convention, and the same launcher portability for the
existing test environment. This explicitly expands the approved paths to the
test up/down/common launcher and a checkout-only frontend-path overlay. Do not
modify real test env files, run test deployments, or change DB/network settings.

Harness up/down share one local resolver: a sibling Compose file in a staged
release takes priority; otherwise use the canonical repository Compose file.
Explicit env paths are caller-relative; omitted env paths default to sibling
`.env`. Preserve the harness project name and detached up; run-sql remains a
compatibility entry point. Down excludes volume/image/orphan deletion. Test
up/down use the same base/dev file set in either layout and remain foreground
for up. A checkout-only overlay reconciles the built frontend path; a release
continues using its bundled frontend-dist. Compose retains normal test project
name resolution including `COMPOSE_PROJECT_NAME` from its env file. The existing
test artifact builder already copies environment files and Compose YAMLs into
`.build/test`; do not run or rewrite that build here.

`PORTAL-HARNESS-LAUNCHER-MODES` makes only the approved launch scripts executable.
`PORTAL-HARNESS-RELEASE` and `PORTAL-HARNESS-RELEASE-OUTPUT` are user-run build/export
pipelines: call the existing image build, export into a new root
`.build/portal-harness` (or an explicit new output directory), and refuse to erase
existing/partial artifacts. Include the image archive, portable scripts, Compose,
public env example, offline SQL artifact, commit/image/source metadata and
checksums. Do not automatically copy real `.env` files or credentials. Export
uses only a uniquely named, network-none, never-started temporary container to
copy the existing image's offline SQL, then removes only that container. Image
save/export is not deployment, schema application or model execution. Generated
release contents are never hand-edited; change authoring sources and re-export
into a new directory. Partial failures preserve evidence and mark the release
incomplete. `PORTAL-HARNESS-RELEASE-LOAD` is target-side, user-run image import.

The agent still must not execute Docker/build/export/load or contact DB/Ollama.
Test portability through fake Docker executables and test export through mocked
subprocess calls into temporary directories. Run the registered source, Node,
shell and diff checks. Real release export, target deployment and session
creation remain user-run evidence, not established by these fixtures.

Local evidence on 2026-11-21: all 35 Python source tests passed, including safe
preset shape, checkout/staged up/down argument resolution for both environments,
mocked release export, existing-output refusal and partial-export cleanup. All
12 Node fixtures passed with one native-stripping skip, and all registered shell
syntax checks passed. The agent only changed executable bits on approved scripts;
no actual `.build` release, Docker operation, real env copy or model/DB call ran.

## Producer/deployable-payload boundary correction

On 2026-11-21 the user clarified that `infra/environments/<name>` is deployable
payload input copied into the final artifact, not a producer/build directory.
They requested better separation and reusable local/CI entry points under
`infra/scripts`. This supersedes placement of the harness release builder and
local-only demo in its environment directory.

Move the release entry point to `infra/scripts/build_env_portal_harness.sh`, its
packaging implementation to `infra/scripts/package_portal_harness_release.py`,
and local demo orchestration to `infra/scripts/run_portal_harness_demo.sh`.
Move producer/portability tests to `infra/scripts/tests`. Keep Dockerfile, source
pins, image-specific build helpers and runtime files in `infra/images`; keep
canonical topology in `infra/compose`. Environment directories contain only
portable lifecycle helpers, target configuration examples and target-facing
documentation. Existing up/down portability and release layout remain unchanged.

`PORTAL-HARNESS-PRODUCER-MOVE` performs one-time guarded renames without overwrites.
Reconcile roots/paths, commands, tests and docs afterward. Make the existing
`build_env_test.sh` entry point and its `_build_target.sh` root lookup independent
of caller cwd; do not otherwise rewrite that legacy builder, execute its cleanup
steps, copy real env files or claim its historical CI job is modernized. The
current `.gitlab-ci.yml` has unrelated obsolete paths/tooling and is not silently
replaced by this task. A shared entry point is a local/CI contract, not proof of
a functioning CI runner or permission to alter deployment.

Run `PORTAL-HARNESS-SOURCE-TESTS`, `INFRA-RELEASE-TESTS`, the registered Node/shell
checks and diff checks. Never hand-edit generated `.build` payloads. No Docker,
real build/export, container restart or DB/model call is executed by the agent.

Verification after the boundary correction: 31 image/runtime Python tests,
7 producer/portability tests and 12 Node fixtures passed, with one host-native
stripping skip. Registered shell syntax checks passed. Producer entry-point tests
use stubs; export/launch tests use fake/mocked Docker. No generated release tree,
real environment configuration, existing deployment or CI job was executed or
modified. The old Portal availability report awaits a fresh user-run startup;
it is not marked resolved by this structural work.

## Approved Portal base and shared release unification

On 2026-11-21 the user explicitly approved replacing the legacy test build and
unifying both products: Portal is the base product; the harness is that same
Portal plus DSH. This supersedes earlier instructions to retain the independent
legacy test builder unchanged. Approval includes the base Dockerfile/build-image
compatibility entry, shared profile-driven release orchestration, portable test
payload export and documentation/tests. The existing task-specific missing
architecture-guide exception remains applicable; no API/application semantics
are changed and no contract regeneration is activated by image restructuring.

The sole Portal recipe lives in `infra/images/portal/`. The harness builds that
base through its registered image helper and extends it with source-pinned DSH,
without rebuilding Portal in a second recipe. The old core-service build entry
delegates to this recipe; its Dockerfile is only a compatibility base alias.
Portal's own settings keep MCP off; the harness launcher retains its agreed
opt-in/anonymous-read defaults and provider/guard/preset configuration.

Both local/CI entry points delegate to one release engine with explicit `test`
and `portal-harness` profiles. Default outputs remain root `.build/test` and
`.build/portal-harness`. Refuse existing paths, including symlinks, before build;
never erase previous output, mutate checkout frontend/source caches, or copy real
env files/credentials. Export offline SQL from the built image through a uniquely
named, network-none, never-started container. The test profile also exports the
image's frontend and source tree to satisfy its existing Compose bind mounts;
target operators still provision env and target-valid mount paths. Copy only
explicit portable payload/Compose files, preserve script modes, record identity,
checksums and completion/failure markers, and retain partial failure evidence.

CI requires Bash, Python 3, Git, Docker/BuildKit and access to the approved image
bases/build dependencies. No host npm build is required by either profile. The
obsolete GitLab job is not claimed operational or silently rewritten. Registered
user-run commands are `PORTAL-BASE-BUILD`, `PORTAL-TEST-RELEASE`,
`PORTAL-TEST-RELEASE-OUTPUT` and the existing harness build/release commands.

For the agent, Docker execution (including inspection), live DB/Ollama calls and
migration application remain prohibited. Run only registered image/release Python,
Node, shell and diff source checks, using fake/mocked Docker and temporary paths.
Real build/export/import, portable target launch, DSH session creation and the
reported Portal 5053 availability remain user-run evidence, not inferred fixes.
Preserve all in-flight work, especially the harness example's user DB/Ollama
values and existing executable modes. Do not edit generated `.build` artifacts.

Unification source evidence on 2026-11-21: 32 image/runtime Python tests and 14
producer/portability tests passed. The release suite exercises both profiles,
build ordering through fake Docker, image-derived mount payloads, checksums,
existing/dangling-output refusal, failure cleanup and the thin harness exporter.
That compatibility exporter was found empty during the user's editor save-conflict
report; its wrapper was restored and a behavioral delegation regression test added.
All 12 Node fixtures passed with one host native-stripping skip. Registered shell
syntax checks passed. The registered mode audit caught the compatibility router's
lost executable bit, restored via `PORTAL-UNIFICATION-EXECUTABLES`; the user's
existing portable launcher modes were not changed. No image was built, inspected,
exported or started; no real env file, DB/Ollama endpoint, generated contract or
existing release output was changed by this unification.

## Approved Compose YAML format reconciliation

On 2026-11-21 the user explicitly requested converting the harness Compose
definition from JSON to the repository's conventional block-style YAML. Rename
the canonical authoring file to `infra/compose/docker-compose-portal-harness.yml`
and reconcile checkout/staged launchers, release profiles, tests and current docs.
Historical move records retain their original filenames. Preserve every parsed
value, including string booleans, interpolation, ports, service/project/volume
identities, bridge and provider/MCP defaults. No deployment change is approved.

`PORTAL-HARNESS-YAML-PREREQUISITE` checks the existing host PyYAML availability;
do not install a missing parser. Source tests now use safe YAML parsing for the
Compose definition and retain JSON for actual JSON sources. Capture the original
normalized JSON hash with `PORTAL-HARNESS-COMPOSE-JSON-BASELINE` before conversion
and assert identical parsed YAML content in regression coverage. Run registered
image/release source tests, shell and diff checks. Docker remains prohibited.

Conversion evidence: existing host PyYAML 6.0.1 was available without installation.
All 33 image/runtime source tests and 14 release/portability tests passed, including
the original normalized-configuration hash and checkout/staged YAML resolution.
The conversion changes no configuration values, real env files, executable modes
or generated release directories. Original JSON paths remain only in historical
move/approval records and the one-time pre-conversion baseline invocation.

## Preset literal-config validation correction

On 2026-11-21 the user-run image reported `preset-standard` validation failure:
the required config ID was missing. The previous patch supplied the entire
EntryGroup configuration as a deferred `!!js` JSON expression rather than a
literal mapping. Correct the patch to expose the required ID and plugin list
directly as ordinary YAML, following the pinned preset declaration shape.
Remove the redundant JSON authoring file and Docker COPY so the patch is the
single source. Preserve the standard ID, safe selected default, disabled coding
presets/plugin manager and exact global MCP allowlist. No provider, backend,
database or public contract semantic change is authorized by this correction.

Regression must parse the actual patch structure without evaluating JavaScript,
assert literal required fields/child lists and retain dangerous-tool exclusions.
All 33 image source tests passed after correction. Run registered Node and diff
checks; actual image build/activation remains user-run because Docker is
prohibited. Portal's separate log still only shows waiting for application
startup, not readiness; do not classify its availability as resolved here.

## Tools-only MCP presentation correction

On 2026-11-21 the user reported denied calls with `server: portal`, followed by
a read of an invented `portal://schemas` resource URI. Pinned
`packages/mcp/mcp-resources/src/{index,tools}.ts` registers generic resource
discovery/read tools and a prompt recommendation when a server registers, even
when it advertises tools only. Portal publishes four tools, not resources.

Disable the optional host `mcp-resources` service in this tools-only profile,
removing its resource tools and prompt. The pinned MCP client declares this
service optional. Keep the four-name guard unchanged; do not invent resources
or broaden access. Clarify exact tool names and ID-based discovery in context.
Run registered source/Node/diff checks without Docker. Actual model behavior and
MCP activation remain user-run evidence. Missing tools must be reported rather
than replaced by guessed resource URIs.

## Upstream comparison research

The user requested an Internet comparison of multi-user behavior in analogous
tools. `PORTAL-HARNESS-UPSTREAM-RESEARCH` permits read-only HTTPS requests to
official documentation and public GitHub repository/content/search APIs for
OpenCode, DeepSeek Harness, OpenHands, LibreChat, Open WebUI, OpenLineage and
the official Model Context Protocol SDK/specification. Substitute an
explicit documentation/API URL for `url`; do not execute downloaded content or
install products. Distinguish community self-hosted, enterprise and cloud
features, browser login from catalog authorization, and history isolation from
execution isolation. Research does not authorize a change of product or deployment.
