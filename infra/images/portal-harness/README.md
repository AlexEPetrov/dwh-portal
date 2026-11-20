# Experimental DWH Portal + source-built DSH

## Scope

This opt-in image packages Portal API, its production frontend, and DeepSeek
Harness **0.2.2-rc.5**. DSH is built from source commit
`9c2670d3bce5275e0d1610272958121af87787bb` (tag `dsh-v0.2.2-rc.5`), not installed
as a published harness package. Existing Portal builds/deployments are unchanged.

The approved approach builds application sources, not the entire compiler and
dependency chain: Python/Node are prebuilt runtimes and third-party dependencies
may contain prebuilt native components. DSH dependencies use its frozen lockfile.

**Not implemented:** catalog MCP, OpenLineage projection, Portal/DSH shared login,
per-user authorization, browser control or production isolation. The default DSH
token authenticates the instance owner, not separate Portal users. The packaging
prototype installs a tool-denial guard; it is not a sandbox or multi-user product.

## Build

From repository root, with Docker BuildKit:

```sh
sh infra/images/portal-harness/build.sh
```

Output: `134/dwh-portal-dsh:0.2.2-rc.5-source-experimental`, **linux/amd64**.
Checked-in DuckDB extensions are amd64; no whole-image arm64 support is claimed.

Stages:

1. Portal frontend: Node 22.21.1, existing npm workspace lockfile; embedded at
   `/app/frontend-dist`. Host environment files are excluded.
2. Portal backend: existing `134/python-builder-313:1.0`, existing requirements
   and offline migration generation.
3. DSH: `node:24.22.2-bookworm` (includes build tools), fixed source commit,
   upstream pnpm 11.28.5, frozen install, official build and runtime-closure
   verification. Deployment uses the same production closure/flags and exported
   relocation validators as upstream's Node carrier. The deployed graph and
   upstream lockfile are retained; the checkout and build tooling are not copied.
4. Runtime: existing `134/python-slim-313:1.0` on RED SOFT UBI8, Portal, Node
   executable, deployed DSH and Web assets. Services run as UID 1001.

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
The unchanged Python requirements may also fail independently on Python 3.13.

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

No database, provider or model request is made. Failure logs redact launch-token
query parameters. This is not a security audit, tool-execution isolation test,
or proof of MCP/user integration.

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
bash infra/images/portal-harness/run-demo.sh
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
Portal memory state is not durable. Configure provider access under DSH Settings
→ Models; the model defaults and supported providers belong to the pinned DSH
version. Do not give this demo production credentials or mount source repositories.

DSH does **not** accept `0.0.0.0` as a bind host. The launcher selects one concrete
container IPv4 address from hostname resolution; if ambiguous, set `DSH_BIND_HOST`.
`DSH_PUBLIC_URL` supplies the advertised browser URL and trusted authority. The
demo sets it to loopback and needs no reverse proxy. Remote deployments need an
explicit approved TLS/forwarding setup; none is configured automatically.

## Runtime configuration

### Existing SQL Portal configuration in the combined image

The SQL store already exists. This launch only connects the combined image to
the existing Portal database; it does not implement another store, create a new
database, run migrations, collect metadata or replace the current deployment.

From repository root, pass the existing Portal environment file:

```sh
bash infra/images/portal-harness/run-sql.sh infra/environments/test/.env
```

Use your actual existing environment file if it differs. Do not paste its
contents or secrets into chat. The script passes it to Compose without sourcing
it as shell code or displaying its resolved contents. [The Compose definition](compose-sql.json)
is JSON (supported by Compose), so its structure is also testable without Docker.

The separate project `dwh-portal-harness` runs a new `portal-harness` service on
the already-defined external `dwh_portal` network. It requires the existing DB
settings; SQL startup/migration validation remains strict. Demo seeding and
reset-on-collect are explicitly disabled. The existing core-service is not
restarted, recreated or stopped. Both instances can read the same Portal DB.

Host ports default to loopback 5053 (Portal) and 3080 (DSH), and a separate
project volume persists DSH state. Stop the old demo first if it occupies these
ports; do not stop the current Portal deployment. Environment overrides
`PORTAL_HARNESS_HOST_PORT` and `DSH_HOST_PORT` select different host ports. If you
change the DSH host port, also set `DSH_PUBLIC_URL` to the actual browser root.
Authentication/token warnings and single-owner limitations remain as above.
Host bind mounts/collector-source mounts from the old deployment are not copied
automatically; this launch targets existing snapshots, not running collectors.

The combined image's environment filter keeps Portal DB/auth settings out of the
DSH process. DSH does not connect to PostgreSQL. Future MCP calls will use Portal
catalog interfaces, not direct database credentials. This SQL launch does not
itself enable MCP or establish per-user authorization.

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
not inherited. Provider variables go only to DSH.

[The patch](dsh.patch.yml) disables HMR and plugin-manager mutation and mounts
[a monotonic tool guard](dsh-guard.mjs), denying model tools until MCP integration
is implemented. Health requires a guard marker matching the running DSH PID.
If the guard has not initialized within 60 seconds, the supervisor stops both
services. This is startup monitoring, not an HTTP admission barrier: do not
expose the listener or give it sensitive credentials while testing. Authenticated
owner APIs are not confined by model-tool guards.

**Shared container, UID, filesystem and network remain shared trust boundaries.**
Native DSH RBAC extension points are not wired to Portal users here. Production
multi-user operation requires a separate design and verification.

## Source-only verification

Run from repository root; requires Python 3.12+ and shell, no third-party packages:

```sh
python3 -B -m unittest discover -s infra/images/portal-harness/tests -v
sh -n infra/images/portal-harness/build.sh
sh -n infra/images/portal-harness/smoke.sh
bash -n infra/images/portal-harness/run-demo.sh
sh -n infra/images/portal-harness/dsh
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

## Upstream evidence

- [Pinned source tree](https://github.com/deepseek-ai/deepseek-harness/tree/9c2670d3bce5275e0d1610272958121af87787bb)
- [Official build graph](https://github.com/deepseek-ai/deepseek-harness/blob/dsh-v0.2.2-rc.5/scripts/build.ts)
- [Runtime-closure deployment](https://github.com/deepseek-ai/deepseek-harness/blob/dsh-v0.2.2-rc.5/scripts/build-exe-for-python-sdk.ts)
- [Web launch and concrete-interface restriction](https://github.com/deepseek-ai/deepseek-harness/blob/dsh-v0.2.2-rc.5/packages/bundle/web-app/README.md)
- [Tool guards](https://github.com/deepseek-ai/deepseek-harness/blob/dsh-v0.2.2-rc.5/packages/core/tools/README.md)
- [Safety notice](https://github.com/deepseek-ai/deepseek-harness/blob/dsh-v0.2.2-rc.5/SAFETY.md)

Execution is registered in [repository policy](../../../rules/policy.yaml) and
[the packaging workflow](../../../rules/workflows/portal-harness-image.md).
