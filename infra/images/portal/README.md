# Portal base image

This is the sole application image recipe for Portal: production frontend,
backend (including Portal-owned MCP), Python dependencies, DuckDB extensions and
offline SQL. The harness image extends this same image with DSH; it does not
maintain another Portal frontend/backend build. MCP is disabled by the ordinary
Portal application defaults. The harness launcher alone supplies its approved
experimental defaults; the base needs no DSH installation or configuration.

From repository root, the image-only build is:

```sh
sh infra/images/portal/build.sh
```

It builds `134/dwh-portal-core-service:1.2` for linux/amd64 using the existing
RED SOFT Python builder/runtime bases and the Node 22.21.1 frontend build stage.
All application compilation occurs inside image builds. The allowlisted context
excludes host environment files, installed dependencies, caches and dist outputs.
Offline SQL generation does not apply migrations or connect to a database.
Runtime serves the embedded frontend and runs the existing API entry point.

The old `backend/core-service/build_image.sh` delegates here, independent of cwd.
The Dockerfile in that directory is only a compatibility alias of an already-built
Portal base, not an independent source build. Use the helper above to build sources.

For release assembly, use the shared producer entry points documented in
`infra/scripts/README.md`. The test profile exports this image; the harness helper
first builds this base and then builds the DSH extension. No Docker operation is
executed by source-only tests; real build/runtime evidence remains user-run.
