"""Full public env coverage without importing settings or reading private envs."""

import ast
import json
import os
import re
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[4]
EXAMPLE = ROOT / "infra/environments/portal-harness/sample.env"
SETTINGS = ROOT / "backend/core-service/src/settings"
COMMON_HEADINGS = [
    "# === 1. Process and HTTP ===",
    "# === 2. Portal snapshot store ===",
    "# === 3. Portal database ===",
    "# === 4. DWH and lineage ===",
    "# === 5. Portal authentication ===",
    "# === 6. Portal AI (legacy) ===",
    "# === 7. Local paths and mounts ===",
]


def example_values():
    """Parse literal assignments only; never source/expand an env file."""
    values = {}
    for line in EXAMPLE.read_text().splitlines():
        match = re.fullmatch(r"([A-Z][A-Z0-9_]*)=(.*)", line)
        if match:
            key, value = match.groups()
            if key in values:
                raise AssertionError("Duplicate public example key: " + key)
            values[key] = value.strip("'\"")
    return values


class EnvironmentExampleTests(unittest.TestCase):
    def test_all_portal_settings_are_documented_or_explicitly_compose_mapped(self):
        values = example_values()
        classes = (
            ("portal.py", "PortalSettings", "APP_PORTAL_"),
            ("portal.py", "DwhCollectorSettings", "APP_DWH_"),
            ("database.py", "DbConnectionSettings", "APP_DB_"),
            ("auth.py", "AuthSettings", "APP_AUTH_"),
            ("ai.py", "AiSettings", "APP_AI_"),
            ("mcp.py", "CatalogMcpSettings", "APP_MCP_"),
        )
        expected = set()
        for filename, class_name, prefix in classes:
            tree = ast.parse((SETTINGS / filename).read_text())
            declaration = next(
                node
                for node in tree.body
                if isinstance(node, ast.ClassDef) and node.name == class_name
            )
            expected.update(
                prefix + node.target.id.upper()
                for node in declaration.body
                if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
            )
        expected.remove("APP_MCP_PUBLIC_BASE_URL")
        self.assertEqual(
            {key for key in values if key.startswith("APP_")}
            - {
                "APP_API_PORT",
                "APP_LOC_REPOSITORY_PATH_HOST",
                "APP_LOC_LOGS_PATH_HOST",
                "APP_DWH_AIRFLOW_DAGS_ROOT_HOST",
                "APP_DWH_PYTHON_MODULES_ROOT_HOST",
            },
            expected,
        )
        compose = yaml.safe_load(
            (ROOT / "infra/compose/docker-compose-portal-harness.yml").read_text()
        )
        environment = compose["services"]["portal-harness"]["environment"]
        self.assertIn(
            "PORTAL_HARNESS_PUBLIC_URL", environment["APP_MCP_PUBLIC_BASE_URL"]
        )
        self.assertIn("PORTAL_HARNESS_PUBLIC_URL", values)

    def test_optional_types_and_existing_runtime_modes_remain_valid(self):
        values = example_values()
        for key in (
            "APP_PORTAL_SEED_DEMO",
            "APP_PORTAL_RESET_ON_COLLECT",
            "APP_AI_ENABLED",
            "APP_DB_ORM_DEBUG_MODE",
            "APP_DB_ORM_PRE_PING",
            "APP_AUTH_SESSION_SECURE_COOKIE",
        ):
            self.assertEqual(values[key], "false", key)
        self.assertEqual(values["APP_PORTAL_STORE"], "sql")
        self.assertEqual(values["APP_MCP_ENABLED"], "true")
        self.assertEqual(values["APP_MCP_ALLOW_ANONYMOUS_READ"], "true")
        self.assertEqual(values["APP_MCP_TOKEN"], "")
        self.assertEqual(
            json.loads(values["APP_MCP_ALLOWED_HOSTS"]),
            ["localhost:*", "127.0.0.1:*", "[::1]:*"],
        )
        self.assertEqual(json.loads(values["APP_MCP_ALLOWED_ORIGINS"]), [])
        self.assertEqual(values["APP_DWH_PSG_HOST"], "")
        self.assertEqual(values["APP_DWH_PSG_DB"], "")
        self.assertEqual(values["APP_DWH_AIRFLOW_DAGS_ROOT"], "")
        self.assertEqual(values["APP_DWH_PYTHON_MODULES_ROOT"], "")
        self.assertEqual(values["APP_DWH_AIRFLOW_LINEAGE_MODE"], "catalog")
        self.assertEqual(values["APP_DWH_PYTHON_MODULES_LINEAGE_MODE"], "catalog")
        for key in ("DSH_BIND_HOST", "DSH_PORTAL_MCP_CREDENTIAL"):
            self.assertEqual(values[key], "")
        self.assertLess(
            int(values["DSH_OLLAMA_MAX_TOKENS"]),
            int(values["DSH_OLLAMA_CONTEXT_WINDOW"]),
        )
        for key in (
            "APP_LOC_REPOSITORY_PATH_HOST",
            "APP_LOC_LOGS_PATH_HOST",
            "APP_DWH_AIRFLOW_DAGS_ROOT_HOST",
            "APP_DWH_PYTHON_MODULES_ROOT_HOST",
        ):
            self.assertEqual(values[key], "")

    def test_common_headings_match_the_registered_private_comment_alignment(self):
        text = EXAMPLE.read_text()
        positions = [text.index(heading) for heading in COMMON_HEADINGS]
        self.assertEqual(positions, sorted(positions))
        test_example = ROOT / "infra/environments/test/sample.env"
        test_text = test_example.read_text()
        self.assertEqual(
            [test_text.index(heading) for heading in COMMON_HEADINGS],
            sorted(test_text.index(heading) for heading in COMMON_HEADINGS),
        )
        test_values = dict(re.findall(r"^([A-Z][A-Z0-9_]*)=(.*)", test_text, re.M))
        for key, value in test_values.items():
            if key in example_values():
                self.assertEqual(value, example_values()[key], key)
        policy = yaml.safe_load((ROOT / "rules/policy.yaml").read_text())
        invocation = policy["verification"]["PORTAL-ENV-ALIGN-TEST-SECTIONS"]["run"]
        for heading in COMMON_HEADINGS:
            self.assertIn(heading, invocation)
        # Run the registered authoring action against a private TEMPORARY fixture,
        # never the real operator file. Every preexisting byte must survive.
        fixture = (
            b"# Existing operator comments\r\nENVIRONMENT=test\r\n"
            b"APP_PORTAL_STORE=sql\r\nAPP_DB_PSG_PASS='fixture-$-secret'\r\n"
            b"APP_DWH_PSG_HOST=\r\nAPP_AUTH_LOCAL_PASSWORD=fixture-auth\r\n"
            b"APP_AI_ENABLED=false\r\nAPP_LOC_SRC_HOST=/fixture/source"
        )
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            private = directory / "infra/environments/test/.env"
            private.parent.mkdir(parents=True)
            private.write_bytes(fixture)
            private.chmod(0o600)
            for _ in range(2):
                result = subprocess.run(
                    ["sh", "-c", invocation],
                    cwd=directory,
                    env={"PATH": os.environ["PATH"]},
                    check=True,
                    capture_output=True,
                    text=True,
                )
                self.assertNotIn("fixture-$-secret", result.stdout + result.stderr)
                self.assertNotIn("fixture-auth", result.stdout + result.stderr)
                updated = private.read_bytes()
                for heading in COMMON_HEADINGS:
                    self.assertEqual(updated.count(heading.encode()), 1)
                    updated = updated.replace(heading.encode() + b"\r\n", b"", 1)
                self.assertEqual(updated, fixture)
                self.assertEqual(stat.S_IMODE(private.stat().st_mode), 0o600)

    def test_private_copy_uses_test_baseline_never_overwrites_and_is_silent(self):
        policy = yaml.safe_load((ROOT / "rules/policy.yaml").read_text())
        invocation = policy["verification"]["PORTAL-ENV-PREPARE-PRIVATE-HARNESS"]["run"]
        fixture = b"APP_DB_PSG_PASS=fixture-private\nAPP_API_PORT=5051\n"
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            source = directory / "infra/environments/test/.env"
            destination = directory / "infra/environments/portal-harness/.env"
            source.parent.mkdir(parents=True)
            destination.parent.mkdir(parents=True)
            source.write_bytes(fixture)
            destination.with_name("sample.env").write_text(
                "APP_DB_PSG_PASS=must-not-replace\nDSH_PROVIDER_MODE=ollama\n"
            )
            # Only git ignore verification is faked. No Docker, real config or DB.
            fake = directory / "git"
            fake.write_text("#!/bin/sh\nexit 0\n")
            fake.chmod(0o700)
            env = {"PATH": f"{directory}:{os.environ['PATH']}"}
            result = subprocess.run(
                ["sh", "-c", invocation],
                cwd=directory,
                env=env,
                capture_output=True,
                check=True,
            )
            self.assertNotIn(b"fixture-private", result.stdout + result.stderr)
            self.assertEqual(source.read_bytes(), fixture)
            copied = destination.read_bytes()
            self.assertTrue(copied.startswith(fixture))
            self.assertNotIn(b"must-not-replace", copied)
            self.assertIn(b"DSH_PROVIDER_MODE=ollama\n", copied)
            self.assertEqual(stat.S_IMODE(destination.stat().st_mode), 0o600)
            destination.write_bytes(b"existing-user-state")
            refused = subprocess.run(
                ["sh", "-c", invocation], cwd=directory, env=env, capture_output=True
            )
            self.assertNotEqual(refused.returncode, 0)
            self.assertEqual(destination.read_bytes(), b"existing-user-state")

    def test_added_portal_settings_reach_only_the_portal_child(self):
        # Reuse the source-only launcher, with its socket boundary avoided by
        # selecting Portal mode. Public example values are never printed.
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "environment_launcher", ROOT / "infra/images/portal-harness/launch.py"
        )
        launcher = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(launcher)
        values = example_values()
        portal = launcher.commands("portal", values)[0]["env"]
        harness = launcher.harness_environment(values)
        for key, value in values.items():
            if key.startswith("APP_"):
                self.assertEqual(portal[key], value, key)
                self.assertNotIn(key, harness)
        self.assertNotIn("DSH_OLLAMA_MODEL", portal)
        self.assertIn("PORTAL_OLLAMA_PROVIDERS", harness)


if __name__ == "__main__":
    unittest.main()
