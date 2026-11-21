# Test environment launch and release layout

This directory is deployable payload input copied into the test release alongside
its images/generated artifacts and Compose files. It contains target lifecycle
helpers, not build/release orchestration. The prepared release needs no source
repository for up/down; its environment and mount paths must suit the target.

`up.sh` and `down.sh` are the same scripts in checkout and release. They select
sibling `docker-compose.yml` and `docker-compose-dev.yml` when copied beside the
artifacts; otherwise they use the canonical repository Compose files. Up keeps
its existing foreground behavior. Down uses the same file set and does not delete
volumes, images or orphans. The project directory is the script directory, not
the caller's working directory; normal Compose project-name configuration,
including `COMPOSE_PROJECT_NAME` from the env file, remains available. Keep the
transferred directory named `test` or set that project name explicitly if renamed.

Both scripts accept one optional env-file path. An explicit path is caller-relative;
the default is `.env` beside the scripts. Do not source configuration as shell code,
commit credentials or paste env contents into diagnostics.

The public template is [sample.env](sample.env), with the same common numbered
sections as the harness environment's [sample.env](../portal-harness/sample.env).
The harness adds MCP/DSH sections; shared Portal settings use the same names and
public development defaults. Neither sample contains the operator's private test
values. Provision `.env` privately; the sample's blank host mount paths and DWH
target are not a ready-to-run production configuration. Test Compose enumerates
its environment keys (unlike the harness's full env-file passthrough), so adding
arbitrary settings to a file does not automatically enable them in this profile.
Use valid target paths for all declared mounts, including the source/wheels
development overlay. Do not copy secrets into either public sample.

```sh
bash infra/environments/test/up.sh
bash infra/environments/test/down.sh
```

Inside a transferred `.build/test` artifact directory:

```sh
./up.sh
./down.sh
```

Before first launch, import `dwh-portal-core-service.img` with Docker and provision
`.env` securely (or pass its path to up/down). Real env files are never included
automatically. The release includes `src`, `frontend-dist`, offline
`migrations/all.sql`, Compose files, metadata/checksums and a completion marker.
Do not deploy a directory marked `RELEASE_FAILED` or missing `RELEASE_COMPLETE`.
SQL is an exported artifact, not an automatically applied migration.

Set `APP_LOC_SRC_HOST` to the bundled `./src` when using the transferred source
mount; set `APP_LOC_WHEELS_HOST` and log/storage/DWH host paths to valid target
locations. Compose resolves relative mount paths against the script/project
directory. Do not transfer workstation-specific absolute paths blindly. No wheels
directory, DB data or model is bundled. The base image already contains the
production frontend and backend; these exported trees support the existing test
Compose bind mounts. The image includes Portal-owned MCP, off by default, without DSH.

In checkout, a source-only Compose overlay points the Portal frontend mount to
the existing `frontend/web/dist` build output. Build that output before running
the checkout deployment. The release uses its bundled `frontend-dist` instead.
Existing env settings still own source/wheel and other mount paths; they must be
valid on the machine where the environment is launched. No DB, network or real
env setting is modified by the launcher portability change. `up-dev.sh` and the
other existing environment utilities are outside this change.

The agent tests argument/path resolution with a fake Docker executable only.
Real image builds, release export, target deploys and DB/model checks are user-run;
the Docker execution prohibition remains in force. Producer instructions belong
to the source repository's `infra/scripts/README.md`, not the target payload.
