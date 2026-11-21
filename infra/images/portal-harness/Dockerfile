# syntax=docker/dockerfile:1

ARG PORTAL_BASE_IMAGE=134/dwh-portal-core-service:1.2
ARG DSH_BUILD_IMAGE=node:24.22.2-bookworm

FROM ${DSH_BUILD_IMAGE} AS harness
USER 0
WORKDIR /build
ENV CI=true \
    DSH_TELEMETRY_DISABLED=1
COPY infra/images/portal-harness/build_dsh.py infra/images/portal-harness/materialize_dsh.mts infra/images/portal-harness/dsh-source.json ./
RUN python3 build_dsh.py

FROM ${PORTAL_BASE_IMAGE} AS runtime
USER 0
ENV HOME=/var/lib/dsh \
    DSH_PORT=3080 \
    DSH_HOME=/var/lib/dsh \
    DSH_AGENTS_HOME=/var/lib/dsh/agents \
    DSH_TELEMETRY_DISABLED=1
WORKDIR /app
COPY --from=harness /usr/local/bin/node /usr/local/bin/node
COPY --from=harness /usr/local/LICENSE /opt/node-LICENSE
COPY --from=harness /opt/dsh/ /opt/dsh/
COPY infra/images/portal-harness/dsh /usr/local/bin/dsh
COPY infra/images/portal-harness/launch.py infra/images/portal-harness/check_dsh_cli.py infra/images/portal-harness/check_dsh_cli.mjs infra/images/portal-harness/dsh-parser-loader.mjs infra/images/portal-harness/healthcheck.py infra/images/portal-harness/container_smoke.py infra/images/portal-harness/dsh.patch.yml infra/images/portal-harness/dsh-guard.mjs infra/images/portal-harness/dsh-source.json infra/images/portal-harness/agent-context.md /opt/portal-harness/
COPY infra/images/portal-harness/tests/test_dsh_parser_loader.mjs infra/images/portal-harness/tests/test_dsh_guard.mjs infra/images/portal-harness/tests/test_dsh_provider_profile.mjs /opt/portal-harness/tests/
COPY infra/images/portal-harness/check_catalog_mcp.mjs /opt/portal-harness/
RUN python3 -c "import os; from pathlib import Path; paths = ['/var/lib/dsh', '/var/lib/dsh/workspace']; [(Path(p).mkdir(parents=True, exist_ok=True), os.chown(p, 1001, 0)) for p in paths]; os.chmod('/usr/local/bin/dsh', 0o755)"
USER 1001:0
# Deliberately fail the build on incompatible UBI8/glibc or incomplete bundles.
RUN node --version && dsh --version && dsh --profile web --patch /opt/portal-harness/dsh.patch.yml --dump-config
RUN node --test /opt/portal-harness/tests/test_dsh_parser_loader.mjs /opt/portal-harness/tests/test_dsh_guard.mjs /opt/portal-harness/tests/test_dsh_provider_profile.mjs && python3 /opt/portal-harness/check_dsh_cli.py
EXPOSE 5051 3080
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD ["python3", "/opt/portal-harness/healthcheck.py"]
ENTRYPOINT ["python3", "/opt/portal-harness/launch.py"]
CMD ["all"]
