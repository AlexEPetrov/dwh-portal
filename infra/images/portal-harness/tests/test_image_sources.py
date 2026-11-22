"""Source-only packaging/supervision checks; Compose parsing requires PyYAML."""

import hashlib
import importlib.util
import json
import os
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

SOURCE = Path(__file__).resolve().parents[1]
REPOSITORY = SOURCE.parents[2]
ENVIRONMENT = REPOSITORY / "infra/environments/portal-harness"
COMPOSE = REPOSITORY / "infra/compose/docker-compose-portal-harness.yml"


def load(name):
    spec = importlib.util.spec_from_file_location(name, SOURCE / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


launcher = load("launch")
smoke = load("container_smoke")
health = load("healthcheck")
with patch.dict(sys.modules, {"launch": launcher}):
    cli_check = load("check_dsh_cli")


class ConfigurationTests(unittest.TestCase):
    def test_catalog_response_guidance_has_twenty_row_limit_and_explicit_navigation(
        self,
    ):
        context = (SOURCE / "agent-context.md").read_text()
        for requirement in (
            "at most 20 data rows",
            "BELOW the table",
            "navigation.portal",
            "navigation.universe",
            "Открыть на портале",
            "Открыть в Universe",
            "not native interactive cards",
            "unfiltered source overview",
        ):
            self.assertIn(requirement, context)
        self.assertIn("do not", context.lower())

    def test_obsolete_sql_wrapper_has_no_registered_execution_path(self):
        policy = yaml.safe_load((REPOSITORY / "rules/policy.yaml").read_text())
        verification = policy["verification"]
        self.assertNotIn("PORTAL-HARNESS-SQL", verification)
        self.assertNotIn("run-sql.sh", json.dumps(verification))
        self.assertEqual(
            verification["PORTAL-HARNESS-UP"]["run_template"],
            'bash infra/environments/portal-harness/up.sh "{env_file}"',
        )

    def test_yaml_conversion_preserves_values_except_approved_launch_and_ipam(self):
        compose = yaml.safe_load(COMPOSE.read_text())
        self.assertEqual(
            compose["services"]["portal-harness"].pop("command"),
            ["${PORTAL_LAUNCH_MODE:-portal}"],
        )
        self.assertEqual(
            compose["networks"]["harness"].pop("ipam"),
            {
                "config": [
                    {
                        "subnet": "${PORTAL_HARNESS_SUBNET:-172.22.0.0/16}",
                        "gateway": "${PORTAL_HARNESS_GATEWAY:-172.22.0.1}",
                    }
                ]
            },
        )
        normalized = json.dumps(compose, sort_keys=True, separators=(",", ":"))
        self.assertEqual(
            hashlib.sha256(normalized.encode()).hexdigest(),
            "c750669cdc80e8747b944c1061a96dd0bceac03d9d5eeabdacc29097bc08ece3",
        )
        self.assertFalse(COMPOSE.with_suffix(".json").exists())

    def test_sql_launch_reuses_configuration_without_replacing_existing_service(self):
        compose = yaml.safe_load(COMPOSE.read_text())
        self.assertEqual(set(compose["services"]), {"portal-harness"})
        service = compose["services"]["portal-harness"]
        self.assertEqual(service["environment"]["APP_PORTAL_STORE"], "sql")
        self.assertEqual(service["environment"]["APP_PORTAL_SEED_DEMO"], "false")
        self.assertEqual(service["environment"]["APP_PORTAL_RESET_ON_COLLECT"], "false")
        self.assertTrue(service["env_file"][0].startswith("${PORTAL_ENV_FILE:?"))
        self.assertTrue(all(port.startswith("127.0.0.1:") for port in service["ports"]))
        self.assertEqual(
            set(compose["networks"]),
            {"harness"},
        )
        self.assertEqual(compose["networks"]["harness"]["driver"], "bridge")
        self.assertEqual(service["networks"], ["harness"])
        self.assertEqual(service["command"], ["${PORTAL_LAUNCH_MODE:-portal}"])
        self.assertNotIn("build", service)
        script = (ENVIRONMENT / "compose.sh").read_text()
        self.assertIn("--project-name dwh-portal-harness", script)
        self.assertIn('--env-file "$PORTAL_ENV_FILE"', script)
        self.assertNotIn("alembic", script)

    def test_launch_selector_sample_defaults_to_portal_without_disabling_mcp(self):
        sample = (ENVIRONMENT / "sample.env").read_text().splitlines()
        self.assertEqual(
            [line for line in sample if line.startswith("PORTAL_LAUNCH_MODE=")],
            ["PORTAL_LAUNCH_MODE=portal"],
        )
        self.assertIn("APP_MCP_ENABLED=true", sample)
        portal = launcher.commands("portal", {})
        self.assertEqual(len(portal), 1)
        self.assertEqual(portal[0]["args"][-1], "/app/src/api/run.py")
        self.assertEqual(portal[0]["env"]["APP_MCP_ENABLED"], "true")

    def test_sql_network_is_project_owned_and_supports_the_host_database(self):
        compose = yaml.safe_load(COMPOSE.read_text())
        service = compose["services"]["portal-harness"]
        self.assertNotIn("network_mode", service)
        self.assertIn("host.docker.internal:host-gateway", service["extra_hosts"])
        for network in compose["networks"].values():
            self.assertNotIn("external", network)
            self.assertNotIn("name", network)
        host_lines = [
            line
            for line in (ENVIRONMENT / "sample.env").read_text().splitlines()
            if line.startswith("APP_DB_PSG_HOST=")
        ]
        self.assertEqual(host_lines, ["APP_DB_PSG_HOST=host.docker.internal"])

    def test_fixed_network_defaults_match_sample_and_narrow_firewall_registration(self):
        import ipaddress

        compose = yaml.safe_load(COMPOSE.read_text())
        sample = dict(
            line.split("=", 1)
            for line in (ENVIRONMENT / "sample.env").read_text().splitlines()
            if line and not line.startswith("#") and "=" in line
        )
        allocation = compose["networks"]["harness"]["ipam"]["config"]
        self.assertEqual(len(allocation), 1)
        for field, key in (
            ("subnet", "PORTAL_HARNESS_SUBNET"),
            ("gateway", "PORTAL_HARNESS_GATEWAY"),
        ):
            self.assertEqual(
                allocation[0][field], "${" + key + ":-" + sample[key] + "}"
            )
            self.assertNotIn(key, compose["services"]["portal-harness"]["environment"])
        network = ipaddress.ip_network(sample["PORTAL_HARNESS_SUBNET"], strict=True)
        gateway = ipaddress.ip_address(sample["PORTAL_HARNESS_GATEWAY"])
        self.assertIn(gateway, network)
        self.assertNotIn(gateway, (network.network_address, network.broadcast_address))
        self.assertEqual(network, ipaddress.ip_network("172.22.0.0/16"))
        policy = yaml.safe_load((REPOSITORY / "rules/policy.yaml").read_text())
        verification = policy["verification"]
        allow = verification["PORTAL-HARNESS-UFW-FIXED-PG-ALLOW"]["run"]
        self.assertEqual(
            allow,
            f"sudo ufw allow in proto tcp from {network} to 172.17.0.1 port 5432",
        )
        self.assertEqual(
            verification["PORTAL-HARNESS-UFW-FIXED-PG-ROLLBACK"]["run"],
            allow.replace("ufw allow", "ufw delete allow", 1),
        )
        # Networking stays in Compose: no fixed per-container IP or firewall side effects.
        self.assertEqual(compose["services"]["portal-harness"]["networks"], ["harness"])
        for name in ("up.sh", "down.sh", "compose.sh", "diagnose-db.sh"):
            self.assertNotIn("ufw", (ENVIRONMENT / name).read_text())

    def test_build_composition_and_environment_files_have_separate_owners(self):
        self.assertTrue((SOURCE / "Dockerfile").is_file())
        self.assertTrue((SOURCE / "build.sh").is_file())
        self.assertTrue((SOURCE / "smoke.sh").is_file())
        self.assertTrue(COMPOSE.is_file())
        for name in (
            "up.sh",
            "down.sh",
            "compose.sh",
            "sample.env",
        ):
            self.assertTrue((ENVIRONMENT / name).is_file(), name)
            self.assertFalse((SOURCE / name).exists(), name)
        self.assertFalse((SOURCE / "compose-sql.json").exists())
        for name in ("build-release.sh", "run-demo.sh", "run-sql.sh"):
            self.assertFalse((ENVIRONMENT / name).exists())
        self.assertTrue(
            (REPOSITORY / "infra/scripts/build_env_portal_harness.sh").is_file()
        )
        self.assertTrue(
            (REPOSITORY / "infra/scripts/package_portal_harness_release.py").is_file()
        )
        self.assertTrue(
            (REPOSITORY / "infra/scripts/run_portal_harness_demo.sh").is_file()
        )

    def test_up_launcher_resolves_compose_and_env_from_another_cwd(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            capture = directory / "arguments"
            fake_docker = directory / "docker"
            fake_docker.write_text('#!/bin/sh\nprintf "%s\\n" "$@" > "$CAPTURE_PATH"\n')
            fake_docker.chmod(0o700)
            env_file = directory / "local settings.env"
            # A shell payload would run if the wrapper sourced the file. It must not.
            marker = directory / "must-not-run"
            env_file.write_text(f'UNTRUSTED=$(touch "{marker}")\n')
            result = subprocess.run(
                ["bash", str(ENVIRONMENT / "up.sh"), env_file.name],
                cwd=directory,
                env={"PATH": f"{directory}:{os.defpath}", "CAPTURE_PATH": str(capture)},
                capture_output=True,
                text=True,
                check=True,
            )
            args = capture.read_text().splitlines()
            self.assertEqual(
                args[:3], ["compose", "--project-name", "dwh-portal-harness"]
            )
            self.assertEqual(args[3:5], ["--env-file", str(env_file)])
            self.assertEqual(args[5], "--file")
            self.assertEqual(Path(args[6]).resolve(), COMPOSE)
            self.assertEqual(args[7:], ["up", "-d"])
            self.assertFalse(marker.exists())
            self.assertEqual(result.stdout, "")

    def test_up_launcher_rejects_missing_environment_without_docker(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            fake_docker = directory / "docker"
            fake_docker.write_text("#!/bin/sh\nexit 99\n")
            fake_docker.chmod(0o700)
            result = subprocess.run(
                ["bash", str(ENVIRONMENT / "up.sh"), "missing.env"],
                cwd=directory,
                env={"PATH": f"{directory}:{os.defpath}"},
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 2)
            self.assertIn("Environment file is missing", result.stderr)

    def test_source_and_toolchain_are_pinned(self):
        release = json.loads((SOURCE / "dsh-source.json").read_text())
        self.assertEqual(release["version"], "0.2.2-rc.5")
        self.assertRegex(release["commit"], r"^[a-f0-9]{40}$")
        self.assertEqual(release["pnpm"], "11.28.5")
        self.assertEqual(release["node"], "24.22.2")
        builder = (SOURCE / "build_dsh.py").read_text()
        self.assertIn('"--frozen-lockfile"', builder)
        self.assertIn('"build:official"', builder)
        self.assertIn('"verify-runtime-closure"', builder)
        self.assertIn('"dsh-python-runtime-closure"', builder)

    def test_profile_installs_guard_and_disables_dynamic_reloading(self):
        patch_text = (SOURCE / "dsh.patch.yml").read_text()
        self.assertIn("id: portal-packaging-guard", patch_text)
        self.assertIn("id: hmr\n  disabled: true", patch_text)
        self.assertIn("id: plugin-manager\n  disabled: true", patch_text)
        self.assertIn("id: mcp-resources\n  disabled: true", patch_text)
        guard = (SOURCE / "dsh-guard.mjs").read_text()
        self.assertIn("ctx.tools.guard(catalogGuard)", guard)
        self.assertNotIn("ctx.tools.restrict(", guard)
        self.assertIn("portal-harness-guard-ready", guard)
        self.assertIn("transport: streamable-http", patch_text)
        self.assertIn("expandTemplates: true", patch_text)
        self.assertNotIn("transport: stdio", patch_text)

    def test_catalog_preset_replaces_nested_coding_tools_instead_of_reenabling_manager(
        self,
    ):
        class PatchLoader(yaml.SafeLoader):
            pass

        # Preserve unrelated runtime expressions as scalar data, never evaluate
        # them. The preset itself MUST be a literal mapping before validation.
        PatchLoader.add_constructor(
            "tag:yaml.org,2002:js", lambda loader, node: loader.construct_scalar(node)
        )
        rows = yaml.load((SOURCE / "dsh.patch.yml").read_text(), Loader=PatchLoader)
        preset = next(row for row in rows if row.get("id") == "preset-standard")[
            "config"
        ]
        self.assertIsInstance(preset, dict)
        self.assertIsInstance(preset["plugins"], list)
        self.assertEqual(preset["id"], "standard")
        self.assertEqual(preset["name"], "Portal catalog")
        self.assertEqual(
            [entry["id"] for entry in preset["plugins"]],
            ["persona", "agent-instructions", "time-context", "compaction"],
        )
        compaction = preset["plugins"][-1]
        self.assertEqual(
            compaction["isolate"], {"compaction": True, "toolResultPruner": True}
        )
        self.assertEqual(
            [entry["id"] for entry in compaction["config"]],
            ["compaction-basic", "tool-result-pruner"],
        )
        serialized = json.dumps(preset)
        for forbidden in (
            "plugin-manager",
            "tool-bash",
            "tool-pwsh",
            "tool-fs",
            "terminal",
            "tool-web",
            "tool-subagent",
            "workflow",
            "tool-skill",
            "tool-office",
            "tool-goal",
            "tool-todo",
        ):
            self.assertNotIn(forbidden, serialized)
        patch_text = (SOURCE / "dsh.patch.yml").read_text()
        self.assertIn("- id: plugin-manager\n  disabled: true", patch_text)
        self.assertNotIn(
            "config: !!js",
            patch_text.split("- id: preset-standard", 1)[1].split(
                "- id: preset-cordis", 1
            )[0],
        )
        self.assertNotIn("catalog-preset.json", patch_text)
        self.assertIn("selectedDefault: standard", patch_text)
        for preset_id in ("preset-cordis", "preset-ptc", "preset-minimal"):
            self.assertIn(f"- id: {preset_id}\n  disabled: true", patch_text)
        self.assertNotIn("catalog-preset.json", (SOURCE / "Dockerfile").read_text())

    def test_build_excludes_local_secrets_and_dependencies(self):
        ignored = (SOURCE / "Dockerfile.dockerignore").read_text().splitlines()
        self.assertIn("**/.env", ignored)
        self.assertIn("**/.env.*", ignored)
        self.assertIn("**/node_modules", ignored)
        self.assertIn("**/.venv", ignored)
        dockerfile = (SOURCE / "Dockerfile").read_text()
        base = (REPOSITORY / "infra/images/portal/Dockerfile").read_text()
        self.assertIn("USER 1001:0", dockerfile)
        self.assertIn("134/python-builder-313:1.0", base)
        self.assertIn("134/python-slim-313:1.0", base)
        self.assertIn("COPY common/contracts/jsonschema/", base)
        self.assertIn("dsh --version", dockerfile)
        self.assertIn("COPY --from=harness /usr/local/bin/node", dockerfile)
        self.assertNotIn("opencode", dockerfile.lower())

    def test_harness_extends_the_same_portal_base_without_an_independent_app_build(
        self,
    ):
        dockerfile = (SOURCE / "Dockerfile").read_text()
        base = (REPOSITORY / "infra/images/portal/Dockerfile").read_text()
        self.assertIn(
            "ARG PORTAL_BASE_IMAGE=134/dwh-portal-core-service:1.2", dockerfile
        )
        self.assertIn("FROM ${PORTAL_BASE_IMAGE} AS runtime", dockerfile)
        for forbidden in (
            "COPY frontend/",
            "COPY backend/",
            "npm ci",
            "pip install",
            "alembic",
        ):
            self.assertNotIn(forbidden, dockerfile)
        self.assertIn("/app/frontend-dist/", base)
        self.assertIn('CMD ["python3", "src/api/run.py"]', base)
        self.assertNotIn("APP_MCP_ENABLED=", base)
        self.assertNotIn("APP_MCP_ALLOW_ANONYMOUS_READ=", base)
        build = (SOURCE / "build.sh").read_text()
        self.assertLess(
            build.index('sh "$ROOT/infra/images/portal/build.sh"'),
            build.index("docker build"),
        )
        compatibility = (REPOSITORY / "backend/core-service/build_image.sh").read_text()
        self.assertIn('exec sh "$ROOT/infra/images/portal/build.sh"', compatibility)
        alias = (REPOSITORY / "backend/core-service/Dockerfile").read_text()
        self.assertIn("FROM ${PORTAL_BASE_IMAGE}", alias)
        self.assertNotIn("COPY ", alias)
        base_ignore = (
            REPOSITORY / "infra/images/portal/Dockerfile.dockerignore"
        ).read_text()
        for pattern in ("**/.env", "**/.env.*", "**/.venv", "**/node_modules"):
            self.assertIn(pattern, base_ignore)

    def test_portal_frontend_copies_shared_package_builder_before_build(self):
        base = (REPOSITORY / "infra/images/portal/Dockerfile").read_text()
        frontend_stage = base.split("AS frontend\n", 1)[1].split("\nFROM ", 1)[0]
        self.assertIn("WORKDIR /build/frontend", frontend_stage)
        self.assertLess(
            frontend_stage.index("COPY frontend/scripts/ ./scripts/"),
            frontend_stage.index("RUN cd web && npm run build"),
        )
        for workspace in ("ui-kit", "app-shell"):
            manifest = json.loads(
                (REPOSITORY / "frontend" / workspace / "package.json").read_text()
            )
            self.assertEqual(
                manifest["scripts"]["build"], "node ../scripts/build-package.mjs"
            )
        self.assertTrue((REPOSITORY / "frontend/scripts/build-package.mjs").is_file())

    def test_every_python_source_parses_without_writing_bytecode(self):
        for path in SOURCE.rglob("*.py"):
            with self.subTest(path=path.name):
                compile(path.read_text(), str(path), "exec")


class CatalogReadinessTests(unittest.TestCase):
    def status(self):
        return {
            "version": 1,
            "pid": 123,
            "global": {
                "state": "ready",
                "available": [
                    "mcp__portal__search_catalog",
                    "mcp__portal__get_object",
                    "mcp__portal__get_lineage",
                    "mcp__portal__get_object_links",
                ],
                "missing": [],
            },
            "last_agent_assembly": {"state": "unknown"},
        }

    def test_host_registration_is_required_but_not_claimed_as_model_admission(self):
        status = self.status()
        with patch.object(health.Path, "read_text", return_value=json.dumps(status)):
            health.check_catalog_registration(123)

    def test_missing_stale_partial_or_unknown_registration_fails_closed(self):
        variants = ["not-json", "null", "{}"]
        for field, value in (
            ("pid", 124),
            ("version", 2),
            ("global", {"state": "unknown"}),
        ):
            status = self.status()
            status[field] = value
            variants.append(json.dumps(status))
        status = self.status()
        status["global"]["available"].pop()
        variants.append(json.dumps(status))
        for value in variants:
            with self.subTest(value=value), patch.object(
                health.Path, "read_text", return_value=value
            ), self.assertRaises(health.CatalogReadinessError):
                health.check_catalog_registration(123)
        with patch.object(
            health.Path, "read_text", side_effect=FileNotFoundError
        ), self.assertRaises(health.CatalogReadinessError):
            health.check_catalog_registration(123)

    def test_guard_marker_alone_cannot_make_harness_healthy(self):
        values = [json.dumps({"mode": "harness", "pid": 123}), "123", "{}"]
        with patch.object(health.Path, "read_text", side_effect=values), patch.object(
            health, "build_opener"
        ) as opener, self.assertRaises(health.CatalogReadinessError):
            health.check()
        opener.return_value.open.assert_not_called()

    def test_prompt_guidance_does_not_require_technical_user_prompts(self):
        context = (SOURCE / "agent-context.md").read_text()
        for phrase in (
            "never require the",
            "any language",
            "descriptions and parameter schemas",
            "never choose the first match",
            "not",
            "cross-language semantic search",
            "catalog access is unavailable",
            "not instructions",
        ):
            self.assertIn(phrase, context)
        patch_text = (SOURCE / "dsh.patch.yml").read_text()
        self.assertIn("never ask for tool", patch_text)
        self.assertIn("- id: mcp-resources\n  disabled: true", patch_text)


class LauncherTests(unittest.TestCase):
    def test_default_provider_mode_is_ollama_with_no_cloud_credentials_or_routes(self):
        environment = launcher.harness_environment(
            {
                "DEEPSEEK_API_KEY": "cloud-secret",
                "OPENAI_API_KEY": "other-cloud-secret",
                "PORTAL_PROVIDER_MODE": "upstream",
                "PORTAL_OLLAMA_PROVIDERS": "untrusted",
            }
        )
        self.assertEqual(environment["PORTAL_PROVIDER_MODE"], "ollama")
        self.assertEqual(json.loads(environment["PORTAL_OLLAMA_PROVIDERS"]), {})
        self.assertNotIn("DEEPSEEK_API_KEY", environment)
        self.assertNotIn("OPENAI_API_KEY", environment)
        self.assertNotIn("PORTAL_OLLAMA_MODEL", environment)

    def test_ollama_profile_is_explicit_and_keeps_key_out_of_model_configuration(self):
        environment = launcher.harness_environment(
            {
                "DSH_OLLAMA_BASE_URL": "http://ollama.internal:11434/v1/",
                "DSH_OLLAMA_MODEL": "test-local-model",
                "DSH_OLLAMA_CONTEXT_WINDOW": "16384",
                "DSH_OLLAMA_MAX_TOKENS": "4096",
                "DSH_OLLAMA_API_KEY": "test-internal-key",
                "DEEPSEEK_API_KEY": "cloud-secret",
            }
        )
        profiles = json.loads(environment["PORTAL_OLLAMA_PROVIDERS"])
        self.assertEqual(set(profiles), {"portal-ollama"})
        profile = profiles["portal-ollama"]
        self.assertEqual(profile["api"], "openai-completions")
        self.assertEqual(profile["baseURL"], "http://ollama.internal:11434/v1")
        self.assertEqual(
            profile["models"],
            [
                {
                    "id": "test-local-model",
                    "contextWindow": 16384,
                    "maxTokens": 4096,
                }
            ],
        )
        self.assertEqual(profile["apiKeyEnv"], "PORTAL_OLLAMA_API_KEY")
        self.assertEqual(environment["PORTAL_OLLAMA_API_KEY"], "test-internal-key")
        self.assertNotIn("test-internal-key", environment["PORTAL_OLLAMA_PROVIDERS"])
        self.assertNotIn("DEEPSEEK_API_KEY", environment)

    def test_upstream_provider_mode_requires_explicit_selection(self):
        environment = launcher.harness_environment(
            {
                "DSH_PROVIDER_MODE": "upstream",
                "DEEPSEEK_API_KEY": "cloud-secret",
            }
        )
        self.assertEqual(environment["PORTAL_PROVIDER_MODE"], "upstream")
        self.assertEqual(environment["DEEPSEEK_API_KEY"], "cloud-secret")
        self.assertNotIn("PORTAL_OLLAMA_PROVIDERS", environment)
        with self.assertRaisesRegex(ValueError, "DSH_PROVIDER_MODE"):
            launcher.commands(
                "all", {"DSH_PROVIDER_MODE": "typo", "DSH_BIND_HOST": "127.0.0.1"}
            )

    def test_partial_or_unsafe_ollama_configuration_is_rejected_without_echoing_secrets(
        self,
    ):
        for configuration in (
            {"DSH_OLLAMA_BASE_URL": "http://ollama.internal:11434/v1"},
            {"DSH_OLLAMA_MODEL": "local-model"},
            {
                "DSH_OLLAMA_BASE_URL": "http://user:private-secret@ollama.internal/v1",
                "DSH_OLLAMA_MODEL": "local-model",
            },
            {
                "DSH_OLLAMA_BASE_URL": "http://ollama.internal/v1?key=private-secret",
                "DSH_OLLAMA_MODEL": "local-model",
            },
            {
                "DSH_OLLAMA_BASE_URL": "file:///tmp/v1",
                "DSH_OLLAMA_MODEL": "local-model",
            },
            {
                "DSH_OLLAMA_BASE_URL": "http://ollama.internal/api",
                "DSH_OLLAMA_MODEL": "local-model",
            },
            {
                "DSH_OLLAMA_BASE_URL": "http://ollama.internal/v1",
                "DSH_OLLAMA_MODEL": "local-model",
                "DSH_OLLAMA_MAX_TOKENS": "99999",
            },
            {
                "DSH_OLLAMA_BASE_URL": "http://ollama.internal/v1",
                "DSH_OLLAMA_MODEL": "local-model",
                "DSH_OLLAMA_CONTEXT_WINDOW": "private-secret",
            },
        ):
            with self.subTest(configuration=list(configuration)):
                with self.assertRaises(ValueError) as error:
                    launcher.harness_environment(configuration)
                self.assertNotIn("private-secret", str(error.exception))

    def test_harness_environment_excludes_portal_credentials(self):
        environment = launcher.harness_environment(
            {
                "PATH": "/bin",
                "APP_DB_PSG_PASS": "database-secret",
                "APP_AUTH_SESSION_SECRET_KEY": "session-secret",
                "APP_MCP_TOKEN": "mcp-secret",
                "PYTHONPATH": "/app/libs",
                "DSH_HOME": "/private-host-home",
                "DSH_EXTRA_FLAGS": "unsafe",
                "NODE_OPTIONS": "--import=/private-host-code.mjs",
                "OPENAI_API_KEY": "provider-secret",
                "HOME": "/private-host-home",
                "UNRELATED_SECRET": "secret",
            }
        )
        self.assertNotIn("APP_DB_PSG_PASS", environment)
        self.assertNotIn("APP_AUTH_SESSION_SECRET_KEY", environment)
        self.assertNotIn("APP_MCP_TOKEN", environment)
        self.assertNotIn("UNRELATED_SECRET", environment)
        self.assertNotIn("PYTHONPATH", environment)
        self.assertNotIn("DSH_EXTRA_FLAGS", environment)
        self.assertNotIn("NODE_OPTIONS", environment)
        self.assertEqual(environment["HOME"], "/var/lib/dsh")
        self.assertEqual(environment["DSH_HOME"], "/var/lib/dsh")

    def test_mcp_uses_local_portal_and_only_passes_a_credential_reference(self):
        environment = launcher.harness_environment(
            {
                "APP_API_PORT": "5151",
                "DSH_PORTAL_MCP_CREDENTIAL": "portal-mcp-owner",
                "APP_MCP_TOKEN": "mcp-secret",
                "PORTAL_MCP_URL": "http://untrusted.invalid/mcp",
            }
        )
        self.assertEqual(environment["PORTAL_MCP_URL"], "http://127.0.0.1:5151/mcp")
        self.assertEqual(environment["PORTAL_MCP_CREDENTIAL"], "portal-mcp-owner")
        self.assertNotIn("mcp-secret", environment.values())
        portal = launcher.commands("portal", {})[0]["env"]
        self.assertEqual(portal["APP_MCP_ENABLED"], "true")
        self.assertEqual(portal["APP_MCP_ALLOW_ANONYMOUS_READ"], "true")
        protected = launcher.commands(
            "portal",
            {"APP_MCP_ALLOW_ANONYMOUS_READ": "false", "APP_MCP_TOKEN": "mcp-secret"},
        )[0]["env"]
        self.assertEqual(protected["APP_MCP_ALLOW_ANONYMOUS_READ"], "false")

    def test_wildcard_bind_is_rejected_before_either_child_starts(self):
        with self.assertRaisesRegex(ValueError, "concrete"):
            launcher.commands("all", {"DSH_BIND_HOST": "0.0.0.0"})

    def test_modes_are_independent(self):
        self.assertEqual(len(launcher.commands("portal", {})), 1)
        harness = launcher.commands("harness", {"DSH_BIND_HOST": "127.0.0.1"})
        self.assertIn("--no-open", harness[0]["args"])
        self.assertIn("--patch", harness[0]["args"])
        self.assertEqual(
            len(launcher.commands("all", {"DSH_BIND_HOST": "127.0.0.1"})), 2
        )

    def test_launcher_flags_precede_every_web_flag(self):
        args = launcher.commands("harness", {"DSH_BIND_HOST": "127.0.0.1"})[0]["args"]
        self.assertEqual(
            args[:5],
            [
                "/usr/local/bin/dsh",
                "--profile",
                "web",
                "--patch",
                "/opt/portal-harness/dsh.patch.yml",
            ],
        )
        for option in (
            "--no-open",
            "--host",
            "--port",
            "--public-url",
            "--trusted-host",
        ):
            self.assertGreater(args.index(option), args.index("--patch") + 1)

    def test_build_time_check_uses_real_launcher_arguments(self):
        environment = {"PATH": "/bin"}
        expected = launcher.commands(
            "harness", {**environment, "DSH_BIND_HOST": "127.0.0.1"}
        )[0]
        with patch.dict(os.environ, environment, clear=True), patch.object(
            cli_check.Path, "mkdir"
        ), patch.object(cli_check.subprocess, "run") as run:
            cli_check.check()
        self.assertEqual(run.call_count, 2)
        self.assertEqual(
            json.loads(run.call_args_list[0].args[0][-1]), expected["args"][1:]
        )
        self.assertEqual(run.call_args_list[1].args[0], [*expected["args"], "--help"])
        self.assertTrue(run.call_args_list[0].kwargs["check"])
        self.assertTrue(run.call_args_list[1].kwargs["check"])

    def test_build_time_check_stops_after_parser_rejects_arguments(self):
        with patch.dict(os.environ, {"PATH": "/bin"}, clear=True), patch.object(
            cli_check.Path, "mkdir"
        ), patch.object(
            cli_check.subprocess,
            "run",
            side_effect=subprocess.CalledProcessError(1, "node"),
        ) as run:
            with self.assertRaises(subprocess.CalledProcessError):
                cli_check.check()
        run.assert_called_once()

    def test_colliding_and_privileged_ports_are_rejected(self):
        with self.assertRaises(ValueError):
            launcher.commands("all", {"DSH_BIND_HOST": "127.0.0.1", "DSH_PORT": "5051"})
        for value in ("80", "0", "65536", "invalid"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                launcher.port(value)

    def test_portal_child_does_not_inherit_harness_keys(self):
        child = launcher.commands(
            "portal", {"DSH_HOME": "/private-host-home", "OPENAI_API_KEY": "secret"}
        )[0]
        self.assertNotIn("DSH_HOME", child["env"])
        self.assertNotIn("OPENAI_API_KEY", child["env"])

    def test_ambiguous_network_requires_explicit_bind(self):
        addresses = [
            (None, None, None, None, ("172.18.0.2", 0)),
            (None, None, None, None, ("172.19.0.2", 0)),
        ]
        with patch.object(launcher.socket, "getaddrinfo", return_value=addresses):
            with self.assertRaisesRegex(ValueError, "DSH_BIND_HOST"):
                launcher.bind_host({})

    def test_single_container_address_is_selected(self):
        addresses = [(None, None, None, None, ("172.18.0.2", 0))]
        with patch.object(launcher.socket, "getaddrinfo", return_value=addresses):
            self.assertEqual(launcher.bind_host({}), "172.18.0.2")

    def test_public_url_with_credentials_is_rejected(self):
        with self.assertRaises(ValueError):
            launcher.commands(
                "harness",
                {
                    "DSH_BIND_HOST": "127.0.0.1",
                    "DSH_PUBLIC_URL": "http://user:secret@example.com/",
                },
            )

    def test_stop_children_terminates_and_reaps_process(self):
        child = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(60)"],
            start_new_session=True,
        )
        try:
            launcher.stop_children([child])
            self.assertIsNotNone(child.poll())
        finally:
            if child.poll() is None:
                os.killpg(child.pid, signal.SIGKILL)
                child.wait()

    def run_launcher(self, directory, programs):
        state = directory / "mode"
        specifications = [
            {"args": program, "cwd": str(directory), "env": dict(os.environ)}
            for program in programs
        ]
        driver = (
            "import importlib.util; from pathlib import Path; "
            f"s=importlib.util.spec_from_file_location('launch', {str(SOURCE / 'launch.py')!r}); "
            "m=importlib.util.module_from_spec(s); s.loader.exec_module(m); "
            f"m.STATE_FILE=Path({str(state)!r}); "
            f"m.commands=lambda mode, env: {specifications!r}; "
            "raise SystemExit(m.main())"
        )
        return subprocess.Popen(
            [sys.executable, "-B", "-c", driver, "portal"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )

    def test_supervisor_stops_sibling_after_failure(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            marker = directory / "sibling.pid"
            sleeper = [
                sys.executable,
                "-c",
                f"import os,time; from pathlib import Path; Path({str(marker)!r}).write_text(str(os.getpid())); time.sleep(60)",
            ]
            failure = [
                sys.executable,
                "-c",
                "import time; time.sleep(0.5); raise SystemExit(7)",
            ]
            child = self.run_launcher(directory, [sleeper, failure])
            try:
                _, stderr = child.communicate(timeout=15)
                self.assertEqual(child.returncode, 7, stderr.decode())
                with self.assertRaises(ProcessLookupError):
                    os.kill(int(marker.read_text()), 0)
            finally:
                if child.poll() is None:
                    child.kill()
                    child.wait()

    def test_supervisor_handles_sigterm(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            child = self.run_launcher(
                directory, [[sys.executable, "-c", "import time; time.sleep(60)"]]
            )
            try:
                deadline = time.monotonic() + 5
                while not (directory / "mode").exists():
                    if child.poll() is not None or time.monotonic() >= deadline:
                        self.fail("Supervisor did not initialize")
                    time.sleep(0.02)
                # The marker precedes handler installation by a few instructions.
                time.sleep(0.1)
                child.terminate()
                _, stderr = child.communicate(timeout=15)
                self.assertEqual(child.returncode, 0, stderr.decode())
            finally:
                if child.poll() is None:
                    child.kill()
                    child.wait()


class SmokeHelpersTests(unittest.TestCase):
    def test_launch_url_is_parsed_without_following_untrusted_hosts(self):
        entry = smoke.launch_url("dsh web: http://127.0.0.1:3080/?token=secret\n")
        self.assertEqual(entry.query, "token=secret")
        self.assertIsNone(smoke.launch_url("still starting"))
        with self.assertRaises(RuntimeError):
            smoke.launch_url("dsh web: https://evil.example/?token=secret")

    def test_diagnostic_redacts_entry_tokens(self):
        self.assertEqual(
            smoke.redact("http://localhost/?token=secret&other=value"),
            "http://localhost/?token=[redacted]&other=value",
        )


if __name__ == "__main__":
    unittest.main()
