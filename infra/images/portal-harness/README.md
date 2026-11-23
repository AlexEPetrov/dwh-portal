# Experimental DWH Portal + source-built DSH

## Scope

This opt-in image packages Portal API, its production frontend, and DeepSeek
Harness **0.2.2-rc.5**. DSH is built from source commit
`9c2670d3bce5275e0d1610272958121af87787bb` (tag `dsh-v0.2.2-rc.5`), not installed
as a published harness package. Portal is the shared base product; this image
adds DSH to that same base. Existing running deployments are not restarted.

The approved approach builds application sources, not the entire compiler and
dependency chain: Python/Node are prebuilt runtimes and third-party dependencies
may contain prebuilt native components. DSH dependencies use its frozen lockfile.

Portal now owns a read-only Streamable HTTP MCP interface; DSH is an ordinary
client, not the parent of an MCP server process. The ordinary Portal defaults
keep MCP disabled. This experimental launcher enables **temporary anonymous
catalog reads** by default, as explicitly requested; see the access warning below.

**Not implemented:** OpenLineage projection, Portal/DSH shared login,
per-user authorization, browser control or production isolation. The default DSH
token authenticates the instance owner, not separate Portal users. The packaging
profile installs an exact catalog-tool guard; it is not a sandbox or multi-user product.

## Repository layout

Image sources, runtime files, the image-build primitive and isolated image smoke stay in
`infra/images/portal-harness/`. The SQL deployment definition is
`infra/compose/docker-compose-portal-harness.yml`. Environment launchers and
the public settings example are deployable payload in `infra/environments/portal-harness/`; see
its [environment guide](../../environments/portal-harness/README.md).

Cross-layer local/CI release orchestration and developer-only trials belong in
`infra/scripts/`, not the target payload. See the
[producer guide](../../scripts/README.md) for the phase boundaries and entry points.

The layout move changes entry-point paths, not project/service names, volumes,
networks, ports or image identity. There is no second deployment definition under
the image sources. Local checks after relocation: all 29 Python packaging tests
and 12 Node fixtures passed; one native-stripping fixture was skipped on the host.
Shell checks passed. Real Docker/container checks remain user-run.

## Build

For a transferable release under repository-root `.build/portal-harness`, use the
[shared local/CI release builder](../../scripts/build_env_portal_harness.sh).
It invokes the image build below and then exports image/deployment artifacts.
Portable lifecycle scripts and release usage are documented in the
[environment guide](../../environments/portal-harness/README.md). The direct image
build alone does not assemble a release directory.

From repository root, with Docker BuildKit:

```sh
sh infra/images/portal-harness/build.sh
```

Output: `134/dwh-portal-dsh:0.2.2-rc.5-source-experimental`, **linux/amd64**.
Checked-in DuckDB extensions are amd64; no whole-image arm64 support is claimed.

Composition (the Portal stages are defined only in `infra/images/portal/Dockerfile`):

1. Portal frontend: Node 22.21.1, existing npm workspace lockfile; embedded at
   `/app/frontend-dist`. Host environment files are excluded.
2. Portal backend: existing `134/python-builder-313:1.0`, existing requirements
   and offline migration generation.
3. DSH: `node:24.22.2-bookworm` (includes build tools), fixed source commit,
   upstream pnpm 11.28.5, frozen install, official build and runtime-closure
   verification. Deployment uses the same production closure/flags and exported
   relocation validators as upstream's Node carrier. The deployed graph and
   upstream lockfile are retained; the checkout and build tooling are not copied.
4. Extension runtime: `FROM 134/dwh-portal-core-service:1.2`, the SAME Portal
   base used by the test release, on RED SOFT UBI8. Add the Node executable,
   deployed DSH/Web assets and harness launcher only. Services run as UID 1001.

The harness build helper builds the shared Portal base first. The base owns MCP
implementation and dependencies but keeps the ordinary disabled defaults; the
harness launcher enables the agreed experimental settings. No independent
frontend/backend recipe or host npm build remains in the harness pipeline.

[Source/toolchain pins](dsh-source.json), [builder](build_dsh.py),
[upstream relocation adapter](materialize_dsh.mts), [Dockerfile](Dockerfile).

Build-time network is required for GitHub, npm/pnpm/pip dependencies and images.
Nothing is installed on the host. There are no runtime `npx` downloads. DSH's
full official source build is substantial: upstream TypeScript steps may use
several GiB of RAM, and dependency downloads require sufficient disk space.
Existing Python base tags and transitive Python dependencies remain mutable;
this is not a bit-for-bit reproducibility claim.

**ABI gate:** DSH/native dependencies are built on Debian, while the final runtime
is UBI8. The final build stage executes Node, DSH version and profile composition
checks. The smoke check exercises actual DSH startup. Missing glibc, libstdc++ or
native compatibility must fail, not be hidden. No such container checks have
been executed yet. If this boundary fails, a compatible RED SOFT Node builder
is the next item to resolve; do not silently replace the production Python base.
The updated Python requirements, including the MCP SDK's native transitive
dependencies, still require a user-run build/ABI check on Python 3.13 and UBI8.

## Offline container smoke

After a successful build:

```sh
sh infra/images/portal-harness/smoke.sh
```

This starts a disposable container with `--network none`, no published ports,
host mounts or real credentials. Portal uses the existing memory/demo store;
DSH explicitly binds loopback for this test. Checks cover:

- Portal health and embedded HTML;
- DSH startup and guard registration;
- anonymous DSH index rejection;
- native launch-token exchange for a cookie and authenticated Web HTML;
- fixed DSH version and graceful shutdown.
- the pinned DSH MCP client SDK connecting to Portal, discovering the exact
  catalog tools and reading search, object/column, lineage and link results.

No database, provider or model request is made. Failure logs redact launch-token
query parameters. This is not a security audit, tool-execution isolation test,
or proof of per-user integration or an actual model tool-call roundtrip. The MCP
probe uses the deployed DSH SDK directly, not a provider/model request.

### Memory-store startup and health

With `APP_PORTAL_STORE=memory`, Portal startup does not validate PostgreSQL
configuration or migrations. `/health` returns HTTP 200 with overall
`status=healthy` and `checks.database.status=skipped`, explicitly noting that the
database check is not applicable. No database session is opened by this check.
With `APP_PORTAL_STORE=sql`, startup still requires current migrations and health
still probes PostgreSQL, returning HTTP 503 if the probe fails. The standalone
migration CLI and explicit DB probe remain strict even when memory is configured.

The user's first smoke attempt on 2026-11-20 exposed the unconditional migration
check. Both startup and health corrections have regression coverage: 19 targeted
tests and all 165 backend unit tests passed on local Python 3.12.3. OpenAPI export
was unchanged. The corrected container smoke has not been rerun by the agent.
Rebuild normally, then rerun the smoke script above; a retained DSH build cache
does not need recompilation for these backend-only changes.

## Local demo

This is the offline memory/demo launch only. For the combined image connected to
the already-working SQL Portal configuration, use the separate launch below.

```sh
bash infra/scripts/run_portal_harness_demo.sh
```

- Portal: <http://127.0.0.1:5053>
- DSH: <http://127.0.0.1:3080>; open the **tokenized URL printed in its logs**.

DSH issues its own cookie after token exchange. The plain root address is not a
substitute for the launch URL on first access. **The launch token and startup logs
are credentials.** Do not publish or paste the unredacted URL. This is different
from password-based authentication and remains separate from Portal login.

The script maps both host ports to loopback only and uses a separate named
volume `dwh-portal-dsh-demo` at `/var/lib/dsh` for DSH credentials, settings and
history. Existing volumes/images from other prototypes are not deleted or reused.
Portal memory state is not durable. The launcher now defaults to the internal
Ollama provider profile described below. Until its URL/model are configured,
UI/MCP work without a model route. Do not give this demo production credentials
or mount source repositories.

DSH does **not** accept `0.0.0.0` as a bind host. The launcher selects one concrete
container IPv4 address from hostname resolution; if ambiguous, set `DSH_BIND_HOST`.
`DSH_PUBLIC_URL` supplies the advertised browser URL and trusted authority. The
demo sets it to loopback and needs no reverse proxy. Remote deployments need an
explicit approved TLS/forwarding setup; none is configured automatically.

## Runtime configuration

### Existing SQL Portal configuration in the combined image

An existing deployment is not required: a private configuration can be prepared
from the public template. The standalone project creates its own bridge with
explicit, per-target subnet/gateway allocation (defaults `172.22.0.0/16` and
`172.22.0.1`). Review Docker/LAN/VPN overlaps before use; see the
[fixed-network transition guide](../../environments/portal-harness/README.md#fixed-project-subnet-and-firewall-alignment).
The network must be recreated to change IPAM; volumes remain preserved. For
an independent staged DB diagnostic that also works when Portal cannot start,
use [diagnose-db.sh](../../environments/portal-harness/diagnose-db.sh) as described
in the [environment guide](../../environments/portal-harness/README.md).
It requires a rebuilt/loaded image containing the diagnostic, not a running
Portal or knowledge of another service. PostgreSQL/schema access remains an
explicit external requirement; no firewall, authentication or migration bypass
is performed.

The SQL store already exists. This launch only connects the combined image to
the existing Portal database; it does not implement another store, create a new
database, run migrations, collect metadata or replace the current deployment.

From repository root, pass the private harness environment file:

```sh
bash infra/environments/portal-harness/up.sh infra/environments/portal-harness/.env
```

Use your actual existing environment file if it differs. Do not paste its
contents or secrets into chat. The script passes it to Compose without sourcing
it as shell code or displaying its resolved contents. [The Compose definition](../../compose/docker-compose-portal-harness.yml)
uses the same YAML format as the other repository Compose files. Source tests
parse it safely with PyYAML without running Docker or resolving real env files.

The separate project `dwh-portal-harness` runs a new `portal-harness` service on
its own Compose-managed bridge network, without requiring the old deployment's
network. It requires the existing DB
settings; SQL startup/migration validation remains strict. Demo seeding and
reset-on-collect are explicitly disabled. The existing core-service is not
restarted, recreated or stopped. Both instances can read the same Portal DB.

For the current host PostgreSQL setup, the environment example uses
`APP_DB_PSG_HOST=host.docker.internal`; Compose supplies the host-gateway alias.
For a future internal DB server, change that setting to its actual DNS name/IP
and adjust the port/credentials as appropriate, then recreate the experimental
service. No image rebuild or network-definition change is needed. See the
[environment guide](../../environments/portal-harness/README.md) for PostgreSQL
listener/access-policy and firewall prerequisites; these are not changed automatically.

Host ports default to loopback 5053 (Portal) and 3080 (DSH), and a separate
project volume persists DSH state. Stop the old demo first if it occupies these
ports; do not stop the current Portal deployment. Environment overrides
`PORTAL_HARNESS_HOST_PORT` and `DSH_HOST_PORT` select different host ports. If you
change the DSH host port, also set `DSH_PUBLIC_URL` to the actual browser root.
Authentication/token warnings and single-owner limitations remain as above.
Compose restores the base Portal frontend, logs, local-storage and read-only
Airflow/Python source mounts. Provision the host/container path pairs in the
private environment file before launch; no paths or credentials are copied from
another deployment automatically. Checkout uses its existing frontend build;
new releases export the matching frontend from the image. These mounts do not
start collectors or expose additional DSH tools. See the environment guide for
mount prerequisites and the single-Python-root limitation.

The combined image's environment filter keeps Portal DB/auth settings out of the
DSH process. DSH does not connect to PostgreSQL. MCP uses Portal catalog services,
not direct database credentials. This experimental SQL launch enables anonymous
read-only MCP by default; it does not establish per-user authorization. If the
Portal host publication changes, set `PORTAL_HARNESS_PUBLIC_URL` to the real
browser origin so returned catalog links do not point to the old port.

DSH has two argument parsers. All launcher options (`--profile`, `--patch`,
configuration dumps) must precede every Web-app option (`--no-open`, `--host`,
`--port`, etc.). The first app option starts verbatim forwarding; a later
`--patch` is rejected by the Web parser even though the launcher supports it.
The launcher now puts its patch before `--no-open`.

[Build-time CLI validation](check_dsh_cli.py) derives the exact same argument
vector as runtime, passes it through the pinned deployed CLI's source parser
using Node's explicit `stripTypeScriptTypes` API, verifies patch consumption,
then runs the Web CLI help. Node forbids automatic TypeScript stripping under
`node_modules`: [the loader](dsh-parser-loader.mjs) instead reads the source,
imports temporary JavaScript outside that tree, keeps the original Commander
dependency and removes the temporary files. Installed upstream files are not
modified, and no TypeScript compiler is installed. This exercises the
launcher/app boundary that a config dump alone does not exercise. Neither check
starts Portal or calls a model.

The launcher supports `all` (default), `portal`, and `harness` modes.

| Setting/path | Meaning |
|---|---|
| `APP_API_PORT` | Portal container port; default 5051 |
| `DSH_PORT` | DSH container port; default 3080 |
| `DSH_BIND_HOST` | Optional concrete local IPv4 override; wildcards rejected |
| `DSH_PUBLIC_URL` | Advertised HTTP(S) root; defaults to loopback and DSH port |
| `/var/lib/dsh` | Persistent DSH home, credentials and session history |

The launcher forwards signals and stops the sibling when a required process
exits. Supplied Docker scripts use `--init` to reap orphaned processes. Harness
environment is allowlisted: Portal `APP_*` settings and ambient Node hooks are
not inherited. Provider variables never go to Portal; cloud-provider environment
variables reach DSH only in the explicitly selected upstream profile.

[The patch](dsh.patch.yml) disables HMR and plugin-manager mutation and mounts
[a monotonic tool guard](dsh-guard.mjs), permitting only the four exact
`mcp__portal__*` catalog tools. General tools and other MCP servers remain denied.
Health requires a guard marker matching the running DSH PID; it is not proof of
MCP connection readiness. The offline smoke probes MCP separately.
If the guard has not initialized within 60 seconds, the supervisor stops both
services. This is startup monitoring, not an HTTP admission barrier: do not
expose the listener or give it sensitive credentials while testing. Authenticated
owner APIs are not confined by model-tool guards.

The user-run 2026-11-20 smoke reached healthy Portal startup but failed with
`DSH tool guard did not initialize`. The initial guard called `tools.restrict()`
from host scope; pinned DSH permits that method only in an agent context and
throws before the guard marker can be written. The correction registers only
the global monotonic execution guard, retaining the exact four-tool allowlist
and writing the readiness marker afterward. The timeout is not increased and
the safety check is not bypassed. This guard restricts execution, not necessarily
the visibility of every agent-scoped tool schema.

Activation fixtures now execute the plugin with a host-context double, reject
illegal restriction use and verify registration/marker failure ordering without
touching the real host marker. Nine Node fixtures and all 22 packaging tests pass;
one Node native-stripping fixture is skipped locally. Rebuild with the normal
build script and repeat the smoke; DSH compilation inputs are unchanged, so its
builder stage can remain cached. No Docker commands were run by the agent.

**Shared container, UID, filesystem and network remain shared trust boundaries.**
Native DSH RBAC extension points are not wired to Portal users here. Production
multi-user operation requires a separate design and verification.

## Catalog-only agent preset

The image replaces the built-in standard coding composition with a literal
mapping in `dsh.patch.yml`, displayed as **Portal catalog**. It retains the `standard`
ID so existing standard-session records need not be rewritten. New sessions use
this selection; the other built-in coding presets are disabled. Persona, the
workspace's catalog instructions, time context and scoped compaction/result
pruning remain. No shell, filesystem tools, delegation, web search or plugin-
management tool is mounted by this preset. The host's Portal MCP tools are
inherited, and the global guard still permits only the four exact catalog names.

The subsequent user-run startup rejected the earlier whole-config `!!js` JSON
expression with a missing required preset ID. The preset declaration is an
EntryGroup: its configuration must expose the required fields as a mapping,
not a deferred whole-object expression. The sole preset authoring source is now
the literal patch mapping; the redundant JSON file/COPY is removed. Source
regression parses the patch without executing its unrelated JavaScript tags and
asserts the literal ID/plugin structure and absent dangerous tool rows. All 33
image source tests pass. Actual pinned DSH activation still requires a rebuild
and user-run startup; source checks are not runtime activation evidence.

This corrects the reported `agent-preset/invalid` error where a preset child
`tool-plugin-manager` waited for the deliberately disabled host plugin manager.
Re-enabling plugin management is not the fix: host flags do not remove nested
preset children. The full safe preset config is now replaced explicitly. The
runtime image must be rebuilt/recreated to load it; DSH compilation inputs are
unchanged. No existing credentials or session volumes are deleted. Old sessions
using a disabled nonstandard preset may need a new Portal catalog chat.

Source tests validate this composition, but actual pinned DSH activation and a
new chat still require the user-run image check. This does not diagnose unrelated
Portal HTTP availability. Portal is published at host loopback port 5053, DSH at
3080; the inherited image's exposed 8080 is not a published Portal host port.

Latest source verification: all 35 Python packaging/release tests and 12 Node
fixtures passed; one native-stripping fixture was skipped. Portable lifecycle
scripts for both environments and release export are tested with fake/mocked
Docker only. New session creation and target Portal readiness remain unverified.

## Internal Ollama and runtime provider selection

`DSH_PROVIDER_MODE=ollama` is the default for the supplied launcher. It disables
the built-in public DeepSeek providers/account UI and the original general pi-ai
provider instance. An independently named adapter exposes only the manually
declared local route; its initial settings namespace does not reuse old cloud
provider profiles. Ambient DeepSeek/OpenAI/etc. environment credentials are not
passed to DSH in this mode. No public inference fallback is configured.

| Launch/environment setting | Meaning |
|---|---|
| `DSH_PROVIDER_MODE` | `ollama` (default) or explicitly `upstream` to restore stock public-provider behavior |
| `DSH_OLLAMA_BASE_URL` | Your internal Ollama OpenAI-compatible base URL, including `/v1`; no credentials/query/fragment |
| `DSH_OLLAMA_MODEL` | Exact ID of an already-installed model on that server |
| `DSH_OLLAMA_CONTEXT_WINDOW` | Context capacity advertised to DSH; default 8192, set to the actual model/server configuration |
| `DSH_OLLAMA_MAX_TOKENS` | Output capacity; default 2048, must be positive and smaller than the context window |
| `DSH_OLLAMA_API_KEY` | Optional dedicated internal gateway key; plain Ollama uses the public placeholder `ollama`, not a cloud credential |

Set these in the existing environment file consumed by the SQL launch (or as
explicit Compose environment overrides), then recreate the experimental service
through the registered SQL launcher. Do not change the existing Portal deployment.
The [environment example](../../environments/portal-harness/sample.env) preserves
the operator's selected URL/model and capacities; adapt them for another target.
The launcher rejects a partially configured pair. Both blank means UI/MCP only,
with no registered model and no model-server request; set both to enable chat.
Use a model that supports tool calling to exercise Portal MCP from a prompt.
Changing these launch parameters requires a restart/recreation; they do not pull
a model, install Ollama, change its server-side context allocation or test its
tool-call compatibility. The conservative capacities above are examples, not
measured capabilities of the selected model. Plain `localhost` refers to the
container; use an internal address reachable from it.

### What "model catalog refresh" means

The reported DeepSeek log is a background request for **available LLM model
names/capabilities** from that provider's `/models` endpoint, with fallback to
a bundled model list. It is not a Portal catalog scan, DB migration or metadata
collector. Ollama mode removes the built-in provider that makes that request;
the local route declares its model explicitly and does not need a public list.
The adapter may still expose its locally installed catalog to configuration UI;
reading that packaged list is not a network refresh or activation of its routes.

This is a **provider configuration profile, not a network sandbox**. Saved
sessions can retain old model selections and fail with unavailable-provider
errors rather than silently switching; start a new chat or select Internal
Ollama. Trusted owner changes can add routes or endpoints in the UI, including
within the new settings namespace. Keep those choices internal. The isolated
deployment must enforce external-egress restrictions separately while allowing
the actual Portal DB and Ollama services. Proxy/NO_PROXY settings must also match
that internal routing. Do not use `upstream` in an isolated runtime.

The container smoke explicitly selects Ollama mode with no URL/model and makes
no inference requests. Local source tests validate parameter handling and our
patch expressions, not actual pinned DSH activation or packet-level isolation.
The image build still requires its existing build-time network/dependency path;
offline runtime operation does not make the build air-gapped.

Local profile checks on 2026-11-21: 26 Python packaging tests and 12 Node fixtures
passed, with one native-stripping fixture skipped. Shell syntax checks passed.
Actual DSH activation, internal Ollama tool calls and network-level isolation
remain unverified until the user runs the updated image in the target contour.

## Portal-owned MCP

### External-chat answers and navigation

DSH remains a separate client. Its catalog guidance now requests a short conclusion
and compact Markdown tables for source/object lists, columns and dependencies.
Display at most **20 data rows per table**. For a larger result, show the first
20 available rows, disclose the shown/total or bounded/incomplete status, and put
**Открыть на портале / Open in Portal** below the table. Do not automatically
fetch all pages to make a larger answer. This is guidance, not deterministic UI
enforcement or a changed API cap; model compliance still needs a user-run chat.

Each successful result preserves canonical `data` and `redacted_fields` and adds
typed `navigation.portal` and `navigation.universe`. Use server-returned URLs,
never model-built paths. Search links open Objects with the same query, database,
schema, type, source, status and changed-since filters, starting at page one.
Portal restores those URL filters and displays removable active filter indicators.
For an object/columns, the Portal link opens its card; for dependencies, its
lineage view. The Universe link focuses the same verified object. Search Universe
links instead open the unfiltered source overview and must be labeled honestly.
Selected-object answers should show both explicit **Открыть на портале** and
**Открыть в Universe** links. Returning links does not open a browser.

Existing `data.links` and the navigation-only tool now include `universe` beside
`object` and `lineage`. The four-tool allowlist, masking/auth/Host/Origin checks,
canonical paging, graph bounds and complete ordered columns remain unchanged.
Configure the actual public Portal origin for the user's browser: a relative link
would otherwise be resolved against the separate DSH origin. Do not infer origins
from request headers or place credentials in URLs. Applying these source changes
requires rebuilding the image containing both Portal and DSH context; existing
chat/model behavior is not established by source tests or SDK smoke alone.

### Pinned DSH UI-extension research (not implemented)

Read-only research used the pinned commit
`9c2670d3bce5275e0d1610272958121af87787bb`, not a newer release:

- [Tool UI documentation](https://github.com/deepseek-ai/deepseek-harness/blob/9c2670d3bce5275e0d1610272958121af87787bb/packages/client/ui-tool/README.md#registering-a-business-tool-view)
  explicitly supports business-owned views keyed by exact wire Tool name, with a
  generic fallback. A Portal plugin can target the four existing qualified names
  without adding a callable model tool or modifying transcript pairing.
- [Tool slot contract](https://github.com/deepseek-ai/deepseek-harness/blob/9c2670d3bce5275e0d1610272958121af87787bb/packages/client/ui-tool/src/client/contract/slots.ts)
  declares the session-scoped `tool.call.toolview` slot and preparing/start/result
  props. It exposes the recorded call/result, disclosure and optional Inspect,
  not a free-form LLM-generated component or blanket backend-execution permission.
- [Business-owned registration example](https://github.com/deepseek-ai/deepseek-harness/blob/9c2670d3bce5275e0d1610272958121af87787bb/packages/client/ui-skill/src/client/index.ts)
  registers `SkillRow` through the same supported slot mechanism.
- [MCP bridge](https://github.com/deepseek-ai/deepseek-harness/blob/9c2670d3bce5275e0d1610272958121af87787bb/packages/mcp/mcp-client/src/tools.ts)
  preserves canonical structured MCP values but also makes a native content
  projection. [Chat projection](https://github.com/deepseek-ai/deepseek-harness/blob/9c2670d3bce5275e0d1610272958121af87787bb/packages/client/ui-chat/src/client/conversation-nodes/tool.ts)
  supplies UI result content/error/meta; it must not be assumed to expose the raw
  `structuredContent` field directly. The next stage needs fixtures against this
  actual projection, using validated Portal JSON result content or a proven typed
  metadata path, never parsing the LLM's prose as authoritative catalog data.
- [Browser loader](https://github.com/deepseek-ai/deepseek-harness/blob/9c2670d3bce5275e0d1610272958121af87787bb/packages/client/web/README.md)
  loads the host-provided client plugin graph and uses shared module identities.
  A client bundle/roster registration must be integrated into the pinned build;
  merely copying our existing host guard plugin will not register browser UI.

Conclusion: a native extension point EXISTS, so a separate browser plugin is a
feasible next stage without replacing DSH or forking the chat renderer. It has
not been built/activated here, and MCP Apps compatibility was not established.
Proposed cards read successful logged catalog results, validate their shape, cap
tables deterministically at 20, and provide trusted Portal/Universe links. Errors,
unknown shapes or interrupted/truncated results retain the generic fallback.
Navigation should use real anchors with safe URL validation, not arbitrary HTML,
scripts, iframe embedding, credentials or automatic collection. No new model
tool, guard broadening or Portal/DSH shared-auth claim is needed for link-only UI.

### Transport and tools

```text
DSH / OpenCode / another compatible MCP client
             │ Streamable HTTP
             ▼
Portal /mcp — official Python SDK in the Portal process
             │ existing catalog query services and serializers
             ▼
Portal catalog snapshots
```

No extra port, Node server SDK, MCP child process or REST loopback hop is used.
Both Portal host entry points own MCP startup/shutdown. DSH connects to
`http://127.0.0.1:5051/mcp` inside the combined container. With the supplied host
publication, another client can use `http://127.0.0.1:5053/mcp`. Host validation
defaults to localhost/loopback authorities; do not disable it to deploy remotely.

| Server tool | Result |
|---|---|
| `search_catalog` | Canonical paged search with typed filters, totals and freshness |
| `get_object` | Full API-exposed object detail, ordered columns and Portal links |
| `get_lineage` | Canonical nodes/edges, unresolved targets, freshness and explicit bounded-snapshot labels |
| `get_object_links` | Existing object/lineage UI links; no browser automation |

Successful tool results contain `data` and `redacted_fields`. Sensitive named
fields (password/token/secret/credentials/authorization/DSN/connection string,
raw extraction/load options) are recursively masked, with their paths listed.
Other metadata remains intact; this is not a general DLP guarantee for secrets
embedded in arbitrary prose. Descriptions/attributes are untrusted data, not
instructions. Errors do not expose provider/DB exception strings.

Lineage preserves stored endpoint directions and types. It is not an execution
log or OpenLineage event stream; no jobs/runs/timestamps are invented. Optional
OpenLineage projection is deferred. The existing demo derived-edge direction
inconsistency is not silently repaired by MCP.

### Ordinary chat: no technical prompts

Ask naturally, for example:

- “Find objects whose names contain ice_brent.”
- “What columns does that table have?”
- “What dependencies are recorded for that object?”
- “Show me its page in Portal.”
- “Найди объекты с ice_brent в названии и покажи их описание.”
- “Какие столбцы есть у этой таблицы?”

The LLM interprets the request, selects tools from their descriptions/input
schemas and uses returned UUIDs for follow-up questions. MCP exposes typed
capabilities and carries validated calls/results; it does not itself interpret
natural language. Portal does not add a language parser, embeddings or model
calls. The configured model must support tool calling; prompts and schema tests
do not prove that a particular Ollama model chooses tools correctly.

Answers should use the user's language while preserving identifiers. Catalog
search remains string matching, not cross-language semantic retrieval. Multiple
plausible matches for one intended object require clarification by qualified
name/schema, not arbitrary first-match selection. Paging, no matches, freshness,
redactions and unresolved bounded lineage must remain explicit.

Tool discovery now describes every parameter and advertises concrete structured
output schemas. Search/detail/columns/lineage reuse existing REST DTOs within the
same success envelope. Requested page size still follows canonical clamping;
returned page size is authoritative. Invalid outputs are sanitized errors.
No new execution or data-access capabilities are introduced.

### Catalog readiness is not process health or model proof

The host guard observes the actual pinned DSH registry, not a second MCP client.
It writes a credential-free, PID-bound, atomically replaced diagnostic at
`/tmp/portal-harness-catalog-status.json` inside the container:

- `global` reports whether all four exact host registrations exist, with
  approved available/missing names only.
- `last_agent_assembly` stays `unknown` until a scoped prompt assembly with a
  step tool set is observed. It then reports that assembly's admitted tools,
  not all sessions or a model response. Registry changes invalidate this evidence.
- `ready` means the corresponding set contains all four tools. It does not mean
  a model selected one or that a catalog read succeeded.

Health now requires actual host catalog registration as well as the guard marker
and protected listener. Missing/stale/incomplete/unknown diagnostics fail catalog
readiness, including in harness-only mode if its Portal connection is unavailable.
Guard activation never waits for MCP and its supervision timeout is unchanged.
A required dynamic agent context uses scope/step visibility to report missing
access rather than invent resources, results or shell/SQL/HTTP fallbacks. Optional
resource discovery remains disabled; the four-name guard is unchanged.

The offline container smoke now checks actual host registration through health,
in addition to its separate SDK protocol checks. It still makes no model call
and does not create an agent. The remaining target-side acceptance check is a
new catalog chat using the ordinary prompts above: confirm actual tool calls
and grounded answers, clarification for ambiguous names, and honest reporting
when catalog access is absent. This requires the rebuilt image, healthy Portal
and the owner's internal tool-capable Ollama configuration. The earlier Portal
startup/availability issue is separate and is not declared fixed here.

### Temporary anonymous-read exception

**Anyone who can reach the enabled anonymous MCP endpoint can read catalog
metadata, including object descriptions, columns, source-file paths and lineage.**
DSH's Web login does not protect that endpoint. Host/Origin checks prevent
certain browser/rebinding attacks; they do not authenticate network clients.
The shared container/network remains a trust boundary. Do not publish this
experimental anonymous mode beyond the approved local trial.

| Setting | Ordinary Portal default / meaning |
|---|---|
| `APP_MCP_ENABLED` | `false`; experimental launcher/Compose default to `true` |
| `APP_MCP_ALLOW_ANONYMOUS_READ` | `false`; experimental launcher/Compose default to `true` temporarily |
| `APP_MCP_TOKEN` | No default; dedicated MCP-only Bearer token when anonymous reads are off |
| `APP_MCP_ALLOWED_HOSTS` | JSON list; localhost/loopback hostnames with any port by default |
| `APP_MCP_ALLOWED_ORIGINS` | JSON list; empty permits requests without Origin, rejects supplied origins |
| `APP_MCP_PUBLIC_BASE_URL` | Empty means relative links; experimental launcher defaults to `http://127.0.0.1:5053` |
| `PORTAL_HARNESS_PUBLIC_URL` | Compose-only override of the public Portal origin for links |
| `DSH_PORTAL_MCP_CREDENTIAL` | Optional **credential reference name**, not a secret value |

To close the exception, set `APP_MCP_ALLOW_ANONYMOUS_READ=false`, configure
`APP_MCP_TOKEN` securely, and restart Portal. Without a token, enabled protected
MCP refuses startup rather than becoming anonymous. Interface disablement is
independent: `APP_MCP_ENABLED=false` returns 404 and does not start the SDK.
Changes require restart; there is no implicit hot-reload of these settings.

In protected mode, clients send `Authorization: Bearer ...` on every MCP request.
The supplied DSH patch supports its native credential templates: save the token
in DSH's credentials provider and set `DSH_PORTAL_MCP_CREDENTIAL` to that reference.
Only the reference reaches raw plugin configuration; `expandTemplates` resolves
it at connection time and redacts resolved values in MCP failure diagnostics.
Do not put token values in that reference, URLs, prompts or command arguments.
The launch filter never forwards `APP_MCP_TOKEN`, DB/auth settings or service
keys to DSH. Protected DSH credential provisioning is operator-owned and has not
been exercised in the user-run container smoke, which intentionally uses no real
credentials. A missing reference value cannot bypass server authentication.

The MCP token is not accepted by Portal's existing REST auth dependency. Existing
REST/UI authentication behavior is otherwise unchanged; this does not claim to
retrofit authorization onto existing REST catalog routes. Read-only MCP exposes
no collection, mutation, SQL, load-history, filesystem, arbitrary URL or shell tools.

## Source-only verification

Run from repository root; requires Python 3.12+, shell and existing PyYAML for
Compose parsing (do not install missing host tools):

```sh
python3 -B -m unittest discover -s infra/images/portal-harness/tests -v
sh -n infra/images/portal-harness/build.sh
sh -n infra/images/portal-harness/smoke.sh
bash -n infra/scripts/run_portal_harness_demo.sh
sh -n infra/images/portal-harness/dsh
bash -n infra/environments/portal-harness/up.sh
node --test infra/images/portal-harness/tests/test_dsh_parser_loader.mjs infra/images/portal-harness/tests/test_dsh_guard.mjs infra/images/portal-harness/tests/test_dsh_provider_profile.mjs
python3 -B -m unittest discover -s infra/scripts/tests -v
```

These exercise configuration/source pins, environment filtering, concrete-IP
selection, URL validation, token redaction and process supervision. Source-text
checks do not prove upstream compilation or runtime behavior. Docker has not
been executed by the agent at the user's request. Build, relocated dependency
graph, native ABI, Web startup and smoke results remain unverified.

On 2026-11-19 all 17 local tests passed, along with shell syntax checks. These
results supersede the earlier packaging prototype's installer tests; no upstream
DSH compilation or container test was executed locally.

On 2026-11-20 a user-run smoke confirmed Portal startup but exposed misplaced
DSH arguments (`unknown option '--patch'`). The ordering correction and build-time
check wiring passed all 20 local packaging tests. The native parser/help probes
are image-build checks and have not been executed by the agent.

The next user build exposed the automatic-TypeScript-loading restriction. After
the explicit loader correction, all 20 Python packaging tests and four Node
loader fixtures passed locally. The native stripping fixture was skipped on
local Node 20.20.2 because that API is unavailable there. The final image build
runs all loader tests on its Node 24 runtime before validating the real parser;
that container check remains unexecuted by the agent.

Latest natural-language usability checks on 2026-11-21: 36 MCP protocol tests,
201 backend unit tests, 37 image-source tests, 14 release fixtures and 16 Node
tests passed, with one host native-stripping skip. Registered shell checks and
both current capability specs passed. OpenAPI export and frontend API generation
left their artifacts unchanged, so no frontend consumer/build change was needed.
Two existing backend deprecation warnings remain. The readiness tests mock actual
registry/step views and marker I/O; they are not pinned-host/model evidence.
No Docker, migrations, live DB or Ollama/model calls were executed by the agent.

## Upstream evidence

Local HTTP MCP verification on 2026-11-20: all 31 MCP tests and all 196 backend
unit tests passed on Python 3.12.3, including official Python SDK HTTP negotiation
in anonymous/token modes through in-process ASGI. OpenAPI export, generated
frontend API and frontend build succeeded; Pydantic's compatible schema drift
was reconciled through generation, not hand edits. Two backend deprecation
warnings and frontend import/chunk warnings remain non-failing. All 22 Python
packaging tests, six Node fixtures and shell checks passed; one native stripping
fixture was skipped on the host. The extended container smoke and DSH model
roundtrip have not been executed by the agent.

- [Pinned source tree](https://github.com/deepseek-ai/deepseek-harness/tree/9c2670d3bce5275e0d1610272958121af87787bb)
- [Official build graph](https://github.com/deepseek-ai/deepseek-harness/blob/dsh-v0.2.2-rc.5/scripts/build.ts)
- [Runtime-closure deployment](https://github.com/deepseek-ai/deepseek-harness/blob/dsh-v0.2.2-rc.5/scripts/build-exe-for-python-sdk.ts)
- [Web launch and concrete-interface restriction](https://github.com/deepseek-ai/deepseek-harness/blob/dsh-v0.2.2-rc.5/packages/bundle/web-app/README.md)
- [Tool guards](https://github.com/deepseek-ai/deepseek-harness/blob/dsh-v0.2.2-rc.5/packages/core/tools/README.md)
- [Safety notice](https://github.com/deepseek-ai/deepseek-harness/blob/dsh-v0.2.2-rc.5/SAFETY.md)

Execution is registered in [repository policy](../../../rules/policy.yaml) and
[the packaging workflow](../../../rules/workflows/portal-harness-image.md).
