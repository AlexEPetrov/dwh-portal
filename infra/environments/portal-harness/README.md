# Experimental Portal + DSH environment

This directory is deployable payload input: portable lifecycle helpers, target
configuration examples and this target-facing guide. It is copied into a release
alongside a generated image archive, Compose definition and release metadata.
There are no image-build or release-assembly entry points here. A target machine
does not need the source checkout, Python packaging scripts or compilers.

## Portable up/down

`up.sh` and `down.sh` work both here in the checkout and beside the staged
release's Compose file, regardless of the caller's working directory. Explicit
env-file paths are relative to the caller. Without an argument they use `.env`
beside the scripts. They never source the env file as shell code.

```sh
bash infra/environments/portal-harness/up.sh infra/environments/portal-harness/sample.env
bash infra/environments/portal-harness/down.sh infra/environments/portal-harness/sample.env
```

The example must be adapted to an existing prepared Portal DB and actual internal
Ollama. Use `up.sh` for startup with an explicit env file or its private default.
Down stops/removes only this Compose project's containers/network; it does
not remove the DSH state volume, image archives, images or PostgreSQL data. The
memory demo is separate and is not managed by this SQL project's down command.

## SQL launch

### Configuration layout

[sample.env](sample.env) is the full single-file development template.
Its common numbered sections match the test environment: process/HTTP, Portal
snapshot store, Portal DB, optional DWH/lineage, Portal auth, legacy Portal AI,
and local paths/mounts. MCP and DSH have additional sections. There is no second
env-file loading protocol; existing up/down/diagnostic invocations are unchanged.
The release already includes this same example, not a second maintained copy.

Copy it to a private untracked configuration before adding real credentials.
For the approved local setup, a private `.env` was prepared from the existing
test configuration's unchanged values plus only missing harness settings. This
is operator-local configuration, not release payload or a public sample. The
private test source was not replaced, and secrets are never copied into samples.
The base Portal host-path keys now configure the same logs, local-storage and
read-only Airflow/Python source mounts here; fixed Compose values still take
precedence. The helper defaults to this
private `.env` when no explicit env-file argument is given.
Public DB/auth credentials and the session signing secret are **development
examples**, not production provisioning. Portal login, DSH Web login and MCP
access are distinct: the retained anonymous-MCP exception is not secured by
either browser login. Configure a dedicated MCP token/reference if closing it.

All current Portal settings are represented, except the direct MCP public-base
setting, which Compose derives from the documented public-origin variable.
Compose's explicit environment values override file values: the SQL/seed/reset
selection and internal listener ports remain fixed. Portal pagination/freshness,
DWH/auth and other settings pass through the env file to the Portal child.
Portal DB/auth/token values are not passed to the DSH child.

DWH host/database and local source roots are blank by default: no DWH target or
Airflow/Python source tree is provisioned by this template. Optional collectors
and the live load journal need their own read-only DWH credentials; source
analysis uses the declared read-only mounts. Before launch, provision existing
absolute target-host paths for logs, local storage, Airflow DAGs and Python
modules, and set both corresponding container source roots in section 4. These
mounts are required even when collection is not requested; blank sample paths
are deliberately not usable deployment defaults. This base-compatible Python
mount supports one root, not a semicolon-separated list. No collection is started
by preparing the file or restoring the mounts. Logs and local storage persist
on the host; the existing named volume independently persists DSH state.

The frontend mount uses the existing built `frontend/web/dist` in checkout and
the image-exported `frontend-dist` beside release scripts, independent of caller
cwd. Checkout requires that frontend build to be present. New harness releases
export it from the same image; old generated releases must not be hand-edited.
There is no backend development-source or wheels overlay in this profile.

The existing operator-selected Ollama endpoint/model/context/output values are
preserved. They are target-specific, not universal recommendations or server
context allocation; change them for another target. The legacy Portal AI section
is separate and remains disabled. Restart/recreate to apply launch configuration;
an already saved DSH model selection may still need explicit reselection.

### Deployment requirements

This is an independent deployment: no previous Portal container, shared Docker
network, neighboring application or knowledge of its settings is required.
The project creates its own bridge. Explicit external requirements are a loaded
matching image, provisioned bind-mount paths/frontend payload, Docker Engine with
Compose/host-gateway support, and a reachable
PostgreSQL database with the current Portal schema and valid credentials.
Ollama is required only for inference, not for the database diagnostic.

Create a private environment file based on [sample.env](sample.env),
setting the actual database address, port, database, user and password. Keep this
file out of version control. It need not come from another deployment. Use the
host alias for a host DB, or real internal DNS/IP for a remote DB as below.

From repository root, supply that file to [up.sh](up.sh):

```sh
bash infra/environments/portal-harness/up.sh infra/environments/portal-harness/.env
```

Use your actual path if it differs. The wrapper also works from another working
directory; its environment-file argument is relative to the caller, and its
Compose-file lookup is relative to the wrapper. The file is passed to Compose,
never sourced as shell code or printed with resolved secrets. Do not commit real
environment files or credentials.

`sample.env` contains host-gateway/PostgreSQL development settings and
the launch-time Ollama/MCP parameters. It is a template, not a prepared SQL
environment. Plain localhost inside Docker is the container, not the host. An
empty PostgreSQL database is not a Portal installation: current Portal schema/
migrations are required. The wrapper does not apply migrations or collect data.

The SQL Compose project/service, dedicated state volume, loopback ports and image
tag remain unchanged. The harness now creates its own project-scoped bridge
network; it does not require the former Portal deployment's network.
Existing deployed services are not modified by the harness launch. Changing a
provider URL/model or port is runtime configuration, not an image rebuild.

### Independent database diagnostic (before or after startup)

After building/loading an image containing this diagnostic, run
[diagnose-db.sh](diagnose-db.sh) with the **same private environment file** used
for startup:

```sh
bash infra/environments/portal-harness/diagnose-db.sh infra/environments/portal-harness/.env
```

It uses a disposable container from the locally installed service image and the
same Compose environment, bridge and host alias. It works before the service has
ever started, including when Portal startup fails. It does not require another
deployment, pull images, start Portal/DSH/dependencies, publish ports, change
firewall/authentication, apply migrations or collect data. Compose may create
its own project network and declared state volume; these are not preconditions.
The one-off container is removed on exit. Normal startup remains unchanged.

The diagnostic prints one JSON object per stage, without settings, credentials,
connection strings or raw driver errors. Numeric destination addresses/ports
and, for successful TCP probes, the container-local source address are included.
That source is before possible host NAT; it does not prove what a remote DB sees.

| Stage / exit code | Meaning and next boundary |
|---|---|
| configuration / 2 | Missing/invalid settings or unavailable image dependencies; no connection attempted |
| dns / 3 | Runtime name/address resolution failed; check the supplied address and runtime DNS/host mapping |
| tcp / 4 | No resolved address accepted TCP; timeout is not a password failure, refusal is not an authentication rejection |
| postgres / 5 | At least one TCP probe passed, but DB connection or read-only query failed; investigate PostgreSQL access policy, credentials, database and TLS; a generic failure does not select one cause |
| schema / 6 | Canonical Portal migration inspection failed, reported mismatched revisions, or lacked required artifacts; not evidence of a TCP failure |
| runtime / 7 | Unexpected diagnostic failure; no raw exception is disclosed |
| result / 0 | All DB stages passed; does not prove Portal HTTP/MCP readiness or a model tool call |

TCP probes try each unique resolved endpoint with a five-second timeout. At
least one success is needed to proceed; all per-endpoint outcomes are retained.
PostgreSQL connections use five-second libpq connection timeouts, read-only
transactions and five-second statement/lock timeouts. These are per-operation,
not a global execution deadline; name resolution follows the OS resolver policy.
Database/schema inspection reuses the image's Portal settings and canonical
migration inspector. There is no alternate version-check algorithm or automatic
repair. A newly created empty DB still needs separately authorized schema setup.

Return only the JSON diagnostic lines for troubleshooting, not the private
environment file or resolved Compose configuration. Docker/Compose errors before
the Python diagnostic starts are outside its sanitization boundary: review and
redact those locally before sharing. The helper propagates the container's exit
code; Docker/Compose can also fail independently (for example a missing image).

### PostgreSQL on the Docker host (current setup)

Set `APP_DB_PSG_HOST=host.docker.internal` in the launch environment file.
The Compose `extra_hosts` mapping resolves it through Docker's `host-gateway`;
the standalone bridge is created by Compose when the user launches the service.
Do not create an empty external `dwh_portal` network as a workaround. The old
Portal deployment and its networks are neither required nor modified.

The host PostgreSQL must listen on an interface reachable from the Docker
bridge, not only `127.0.0.1`. Its `pg_hba.conf` and host firewall must allow the
actual container/bridge source range and the intended DB/user, using the normal
authentication policy. Do not open access to all addresses or disable auth.
The bridge now has explicit IPAM, described below. These server/firewall
prerequisites are operator tasks, not changes made by this launcher or by the
agent. A host-gateway alias alone cannot make a loopback-only PostgreSQL listener
reachable.

### Fixed project subnet and firewall alignment

Compose uses `PORTAL_HARNESS_SUBNET` (default `172.22.0.0/16`) and
`PORTAL_HARNESS_GATEWAY` (default `172.22.0.1`). These Compose-only settings use
the same private env file as up/down/diagnostics, not a second configuration
protocol. Existing private files without the keys receive the explicit defaults.
Changing either value requires recreating the project network; restarting a
container does not change network IPAM. Container addresses remain automatic;
there is no external/shared network or fixed global network name.

**Before first use or migration**, reserve a non-overlapping range on the target.
The defaults match the reported current Docker allocation, not a universal safe
range. Review every Docker network and host LAN/VPN route on the Docker host:

```sh
docker network inspect $(docker network ls -q) --format '{{.Name}} {{json .IPAM.Config}}'
ip -4 route show table all
```

The current project's own allocation/route is expected to match. Any overlap
with another Docker network or LAN/VPN destination must be resolved before
creation. Consult the operator's reserved/offline VPN ranges too; missing routes
are not proof an allocation is free. If a command is unavailable, stop and obtain
allocation evidence rather than installing tools or guessing another range.
For a different target, set both keys in its private env file and coordinate
corresponding PostgreSQL/firewall policy before launch. Gateway must be a usable
address inside the chosen subnet. Do not change the global Docker address pools.

For the reported host only, the PostgreSQL destination is `172.17.0.1:5432` via
`host.docker.internal`. **It is not the project gateway `172.22.0.1`.** Preserve
the host-gateway mapping and DB host setting. With the confirmed/reserved
`172.22.0.0/16` source allocation, the registered user-run narrow allow is:

```sh
sudo ufw allow in proto tcp from 172.22.0.0/16 to 172.17.0.1 port 5432
```

This rule allows one destination/port, not all host services. Keep existing
`172.19.0.0/16` rules until their ownership is established. Do not disable UFW
or PostgreSQL authentication. If this operation actually added a new rule, its
exact rollback is:

```sh
sudo ufw delete allow in proto tcp from 172.22.0.0/16 to 172.17.0.1 port 5432
```

If UFW skipped an already existing rule, do not delete that preexisting rule as
rollback. These concrete firewall actions apply only to the observed source and
destination; a changed target needs separately reviewed/registered commands.
For a remote PostgreSQL server, the observed source may be host-NATed instead.

#### Transition and acceptance (operator-run)

Use the updated canonical checkout configuration or a newly generated release;
never hand-edit an old generated release. No image rebuild is required by IPAM
itself. Preserve the same project name and private env path. Record the previous
allocation/settings and firewall changes locally for rollback, without sharing
secrets. After allocation review and the narrow firewall change above:

```sh
bash infra/environments/portal-harness/down.sh infra/environments/portal-harness/.env
bash infra/environments/portal-harness/diagnose-db.sh infra/environments/portal-harness/.env
docker network inspect dwh-portal-harness_harness --format '{{json .IPAM.Config}}'
bash infra/environments/portal-harness/up.sh infra/environments/portal-harness/.env
```

Run each step separately and inspect its result. Down removes only this project's
containers/network and preserves the named DSH state volume. Stop if network
removal fails due to attached containers: their owner must stop their one-off
jobs; do not force-disconnect unrelated containers or prune networks. The
diagnostic recreates the project network using the same explicit IPAM even when
Portal cannot start. Confirm the allocation and all diagnostic stages before up.
An allocation conflict or failed DB diagnostic blocks acceptance; do not bypass
startup/migration checks. In a new transferred release use the sibling down,
diagnostic and up helpers with the same private env, as below.

Check successful Portal startup/health, all four actual DSH catalog registrations,
then a real tool call in a new chat. For chat, explicitly select
`PORTAL_LAUNCH_MODE=all`; the retained default `portal` intentionally does not
start DSH. DB diagnostic success alone proves neither MCP nor model behavior.
Repeat project down/diagnostic recreation when testing that IPAM stays stable.
These are target-side checks, not actions performed by the agent.

Rollback is an operator-reviewed recreation with the previous approved allocation
and matching firewall policy, preserving volumes; the previous broken firewall
alignment is not a known-good recovery target. Undo only the newly added UFW rule
after abandoning this allocation and confirming no consumer still needs it.

### PostgreSQL on another internal server (future setup)

Change `APP_DB_PSG_HOST` in the same environment file to the server's actual
internal DNS name/IP. Adjust `APP_DB_PSG_PORT` if its port differs, and use the
appropriate existing database/user/credential settings. The launcher passes
these values through unchanged. No image rebuild, new Compose network or change
to `host.docker.internal` mapping is needed; that mapping is simply unused for
the remote database.

The container must have internal DNS/routing to that server, and its PostgreSQL
listener, access policy and firewalls must permit the actual client source
(possibly NATed by the Docker host). Keep the contour's egress policy restricted
to approved destinations. A bridge network is not an Internet-egress firewall.
Restart/recreate the experimental service through the same SQL launcher to pick
up environment changes. This does not create the Portal schema or apply migrations.

## Using a transferred release

A prepared release contains the image archive, Compose definition, the same
portable up/down/common scripts, [diagnose-db.sh](diagnose-db.sh), public env example,
this guide, offline migration SQL, commit/image/source metadata and checksums.
Frontend and application code are embedded in the image. Use only a directory
marked `RELEASE_COMPLETE`; `RELEASE_FAILED` indicates an incomplete export.
Never patch generated image/Compose artifacts to repair their authoring sources.

Real `.env` files are deliberately not copied into the harness release automatically. After
transferring the complete release directory, provision the target's configuration
securely as `.env` beside the scripts or pass its explicit path. Do not commit
credentials. Import the image through the registered target-side load procedure;
from inside the transferred directory the equivalent commands are:

```sh
docker load --input ./dwh-portal-dsh.img
bash ./diagnose-db.sh ./.env
./up.sh ./.env
./down.sh ./.env
```

These are target-side user commands, not commands executed by the agent. The
target needs Docker/Compose and access only to its approved DB/Ollama endpoints,
not the source repository or a compiler. The image must already match the target
architecture/runtime. A release export does not prove actual target deployment.

## Target runtime settings and access

The supplied example exposes Portal on loopback 5053 and DSH on loopback 3080.
Open the DSH tokenized launch URL from its logs; that URL is a credential and
must not be shared unredacted. A running container or `health: starting` status
does not prove Portal startup completed. The image's exposed 8080 is not a
published Portal host port.

`DSH_PROVIDER_MODE=ollama` disables the built-in public inference profiles.
Configure `DSH_OLLAMA_BASE_URL` with the actual internal OpenAI-compatible `/v1`
URL and `DSH_OLLAMA_MODEL` with an installed tool-capable model. Both unset means
UI/MCP without inference; there is no cloud fallback. Context/output parameters
must match the actual server/model. A Compose bridge/provider profile is not an
egress firewall: the contour's network policy must enforce approved destinations.

The current experimental settings explicitly allow anonymous read-only MCP.
Anyone reaching that endpoint can read catalog metadata. DSH Web authentication
does not protect it. To close this exception, disable anonymous reads and provide
a dedicated MCP token before restart; no DB or general Portal credentials belong
in DSH model prompts. The Portal catalog preset omits coding/plugin-management
tools; it is not an operating-system sandbox or per-user isolation boundary.
