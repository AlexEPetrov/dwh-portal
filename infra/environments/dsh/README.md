# Independent DSH-only deployment

This target runs only DSH from the existing combined Portal + DSH image. It does
not start Portal, connect to PostgreSQL, load a Portal environment file or mount
Portal sources. No separate DSH image recipe exists. Portal runs independently
on the other machine and owns the read-only Streamable HTTP MCP endpoint.

## Configuration and prerequisites

Use [sample.env](infra/environments/dsh/sample.env) as the public template and
provision a private environment file securely. It must contain an explicit
remote MCP endpoint; there is intentionally no guessed server address/default.
The URL must use HTTP(S), include the actual MCP path and contain no embedded
credentials, query or fragment. The launcher rejects invalid input before
starting a child and reports a fixed error without echoing the URL. Never print
resolved Compose configuration or share logs containing tokenized Web URLs.

The Portal operator must separately establish:

- a healthy Portal with MCP enabled, reachable from the DSH container's network;
- an appropriately bound/published listener (a Portal host-loopback publication
  is NOT remotely reachable), DNS/routes and narrowly scoped access policy;
- explicit MCP Host/Origin allowlists matching the actual endpoint and trusted
  origins; retain validation rather than allowing every host/origin;
- preferably protected MCP using a dedicated MCP-only bearer token, provisioned
  through DSH's credential provider. The credential setting is a reference NAME,
  not the token. Portal browser cookies/service keys are not substitutes;
- Portal's public browser origin for returned Portal/Universe links, reachable
  by the person using chat, independently of the container's MCP endpoint.

Existing temporary anonymous-read MCP, if deliberately retained by its owner,
exposes metadata to anyone reaching that endpoint; DSH Web login does not protect
it. This profile neither enables anonymous access nor alters server policy.
Configure actual listeners, TLS/trust, routing and firewall outside these scripts;
they do not open remote ports or modify Portal/DB/firewall settings.

The default provider is internal Ollama. Supply both the real OpenAI-compatible
/v1 endpoint and an installed tool-capable model ID, or neither for UI/MCP only.
There is no automatic cloud fallback. Match context/output limits to the actual
model server. The upstream provider choice is an explicit opt-in; this Compose
allowlist does not forward arbitrary host cloud-provider credentials. A profile
is not an egress firewall: separately enforce approved Portal/model destinations.

## Portable lifecycle

From repository root, after loading the matching image and preparing the private
configuration, use [up.sh](infra/environments/dsh/up.sh) and
[down.sh](infra/environments/dsh/down.sh). Both accept one optional environment
path, caller-relative; otherwise they use the private file beside the scripts.
They work from any working directory, preferring the sibling release Compose
definition over the checkout definition. They never source the file as shell.

The independent project is `dwh-dsh`; its project-owned bridge and state volume
are separate from `dwh-portal-harness`. DSH publishes only host loopback 3080 by
default. On one host, choose a different host port/public browser origin if the
combined deployment already occupies it. No automatic remote Web exposure is
provided. The Web UI retains token/cookie authentication and single-owner limits;
the tokenized launch URL is a credential. Down preserves state/images and does
not stop Portal, delete volumes or remove unrelated containers.

Health in harness mode checks the DSH listener/auth fence, PID-bound tool guard
and registration of all four catalog tools, without probing a local Portal or
making a separate remote MCP request. Remote failure leaves catalog readiness
unhealthy; it does not permit general tools or disable authentication. Process
startup alone does not establish a model roundtrip or remote catalog readiness.

## Release

The producer [build_env_dsh.sh](infra/scripts/build_env_dsh.sh) uses the shared
profile-driven pipeline, rebuilding the same combined image and exporting a new
`.build/dsh` by default. Its optional output argument must be a new path. The
release contains the shared image archive, DSH Compose, these portable scripts,
public template, guide, image/source metadata, checksums and completion marker.
It has no frontend/source payload, migrations or DB diagnostic. Since no image
files are needed, export does not create a temporary container for this profile.
The combined image itself still contains Portal binaries/offline artifacts; this
is process/deployment separation, not a reduced image or OS security sandbox.

After transfer, use the same sibling scripts and provide private configuration
separately. Do not edit generated releases, reuse failed/partial output or assume
a source test proves export/import/startup. Build/export/load, remote reachability,
credential provisioning, catalog registration and actual model calls remain
user-run acceptance evidence.
