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
bash infra/environments/portal-harness/up.sh infra/environments/portal-harness/sql.env.example
bash infra/environments/portal-harness/down.sh infra/environments/portal-harness/sql.env.example
```

The example must be adapted to an existing prepared Portal DB and actual internal
Ollama. `run-sql.sh` remains a compatibility alias for up with an explicit env
file. Down stops/removes only this Compose project's containers/network; it does
not remove the DSH state volume, image archives, images or PostgreSQL data. The
memory demo is separate and is not managed by this SQL project's down command.

## SQL launch

From repository root, supply the actual existing Portal environment file:

```sh
bash infra/environments/portal-harness/run-sql.sh infra/environments/test/.env
```

Use your actual path if it differs. The wrapper also works from another working
directory; its environment-file argument is relative to the caller, and its
Compose-file lookup is relative to the wrapper. The file is passed to Compose,
never sourced as shell code or printed with resolved secrets. Do not commit real
environment files or credentials.

`sql.env.example` contains host-gateway/PostgreSQL development settings and
the launch-time Ollama/MCP parameters. It is a template, not a prepared SQL
environment. Plain localhost inside Docker is the container, not the host. An
empty PostgreSQL database is not a Portal installation: current Portal schema/
migrations are required. The wrapper does not apply migrations or collect data.

The SQL Compose project/service, dedicated state volume, loopback ports and image
tag remain unchanged. The harness now creates its own project-scoped bridge
network; it does not require the former Portal deployment's network.
Existing deployed services are not modified by the harness launch. Changing a
provider URL/model or port is runtime configuration, not an image rebuild.

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
Docker may choose the bridge subnet; this configuration does not assume a fixed
CIDR. These server/firewall prerequisites are operator tasks, not changes made
by this launcher or by the agent. A host-gateway alias alone cannot make a
loopback-only PostgreSQL listener reachable.

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
portable up/down/common scripts, compatibility launcher, public env example,
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
