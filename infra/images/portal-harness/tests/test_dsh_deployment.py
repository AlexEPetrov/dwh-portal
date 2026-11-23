"""Independent-mode source checks; no Docker, remote MCP, database or model I/O."""

import importlib.util
import json
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from urllib.error import HTTPError

import yaml

SOURCE = Path(__file__).resolve().parents[1]
ROOT = SOURCE.parents[2]


def load(name):
    spec = importlib.util.spec_from_file_location(name, SOURCE / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


launch = load("launch")
health = load("healthcheck")


class IndependentDshTests(unittest.TestCase):
    def test_harness_requires_explicit_url_before_starting_any_child(self):
        with patch.object(launch.subprocess, "Popen") as child, patch.object(
            launch.sys, "argv", ["launch.py", "harness"]
        ), patch.dict(
            launch.os.environ, {"DSH_BIND_HOST": "127.0.0.1"}, clear=True
        ), patch(
            "builtins.print"
        ):
            self.assertEqual(launch.main(), 2)
            child.assert_not_called()

    def test_remote_http_https_and_ipv6_are_preserved_with_credential_reference(self):
        for url in (
            "https://portal.example.test/mcp",
            "http://portal.example.test:5051/mcp/",
            "https://[2001:db8::1]:8443/mcp",
        ):
            with self.subTest(url=url):
                children = launch.commands(
                    "harness",
                    {
                        "DSH_BIND_HOST": "127.0.0.1",
                        "DSH_PORTAL_MCP_URL": url,
                        "DSH_PORTAL_MCP_CREDENTIAL": "catalog-reference",
                        "APP_API_PORT": "not-a-portal-process",
                        "APP_DB_PSG_PASS": "db-secret",
                        "APP_MCP_TOKEN": "server-secret",
                        "APP_LOC_SRC_HOST": "/private/source",
                        "DEEPSEEK_API_KEY": "cloud-secret",
                    },
                )
                self.assertEqual(len(children), 1)
                self.assertEqual(children[0]["args"][0], "/usr/local/bin/dsh")
                environment = children[0]["env"]
                self.assertEqual(environment["PORTAL_MCP_URL"], url)
                self.assertEqual(
                    environment["PORTAL_MCP_CREDENTIAL"], "catalog-reference"
                )
                self.assertFalse(any(key.startswith("APP_") for key in environment))
                for secret in (
                    "db-secret",
                    "server-secret",
                    "cloud-secret",
                    "/private/source",
                ):
                    self.assertNotIn(secret, environment.values())

    def test_invalid_urls_have_fixed_redacted_errors(self):
        for url in (
            "",
            " ",
            "file:///private/secret",
            "portal.example.test/mcp",
            "https://user:secret@portal.example.test/mcp",
            "https://portal.example.test/mcp?token=secret",
            "https://portal.example.test/mcp#secret",
            "https://portal.example.test/mcp?",
            "https://portal.example.test/mcp#",
            "http://[secret/mcp",
            "https://portal.example.test:secret/mcp",
            "https://portal.example.test:65536/mcp",
            "https://portal.example.test:0/mcp",
            "https:///mcp",
            "https://portal.example.test/\nsecret",
            "https://portal.example.test/ secret",
        ):
            with self.subTest(url=url), self.assertRaises(ValueError) as error:
                launch.portal_mcp_url({"DSH_PORTAL_MCP_URL": url}, required=True)
            self.assertEqual(
                str(error.exception),
                "DSH_PORTAL_MCP_URL must be an explicit HTTP(S) URL without credentials, query or fragment",
            )

    def test_combined_and_portal_defaults_remain_local(self):
        children = launch.commands(
            "all", {"DSH_BIND_HOST": "127.0.0.1", "APP_API_PORT": "6061"}
        )
        self.assertEqual(
            children[-1]["env"]["PORTAL_MCP_URL"], "http://127.0.0.1:6061/mcp"
        )
        self.assertEqual(len(launch.commands("portal", {})), 1)

    def test_compose_has_only_dsh_settings_state_and_port(self):
        config = yaml.safe_load(
            (ROOT / "infra/compose/docker-compose-dsh.yml").read_text()
        )
        self.assertEqual(set(config["services"]), {"dsh"})
        service = config["services"]["dsh"]
        self.assertEqual(
            service["image"], "134/dwh-portal-dsh:0.2.2-rc.5-source-experimental"
        )
        self.assertEqual(service["command"], ["harness"])
        self.assertNotIn("env_file", service)
        self.assertNotIn("build", service)
        self.assertNotIn("depends_on", service)
        self.assertEqual(service["volumes"], ["dsh-state:/var/lib/dsh"])
        self.assertEqual(service["ports"], ["127.0.0.1:${DSH_HOST_PORT:-3080}:3080"])
        self.assertTrue(all(key.startswith("DSH_") for key in service["environment"]))
        self.assertTrue(
            service["environment"]["DSH_PORTAL_MCP_URL"].startswith(
                "${DSH_PORTAL_MCP_URL:?"
            )
        )
        self.assertEqual(config["volumes"], {"dsh-state": {}})
        self.assertEqual(config["networks"], {"dsh": {"driver": "bridge"}})
        template = (ROOT / "infra/environments/dsh/sample.env").read_text()
        keys = {
            line.split("=", 1)[0]
            for line in template.splitlines()
            if line and not line.startswith("#")
        }
        self.assertTrue(all(key.startswith("DSH_") for key in keys))
        self.assertIn("DSH_PORTAL_MCP_URL=\n", template)
        self.assertIn(
            ".env",
            (ROOT / "infra/environments/dsh/.gitignore").read_text().splitlines(),
        )
        policy = yaml.safe_load((ROOT / "rules/policy.yaml").read_text())
        paths = policy["topics"]["portal-harness-image"]["paths"]
        for path in (
            "infra/environments/dsh/**",
            "infra/compose/docker-compose-dsh.yml",
            "infra/scripts/build_env_dsh.sh",
        ):
            self.assertIn(path, paths)

    def test_health_checks_only_local_dsh_and_still_requires_catalog_and_guard(self):
        state = {"mode": "harness", "pid": 123, "host": "127.0.0.1", "port": "3080"}
        opener = Mock()
        opener.open.side_effect = HTTPError("local", 401, "auth required", {}, None)
        with patch.object(
            health.Path, "read_text", side_effect=[json.dumps(state), "123"]
        ), patch.object(health, "build_opener", return_value=opener), patch.object(
            health, "check_catalog_registration"
        ) as registration:
            health.check()
            registration.assert_called_once_with(123)
            opener.open.assert_called_once_with("http://127.0.0.1:3080/", timeout=3)
        for marker, catalog_failure in (("stale", False), ("123", True)):
            with self.subTest(marker=marker), patch.object(
                health.Path, "read_text", side_effect=[json.dumps(state), marker]
            ), patch.object(health, "build_opener", return_value=opener), patch.object(
                health,
                "check_catalog_registration",
                side_effect=(
                    health.CatalogReadinessError("missing") if catalog_failure else None
                ),
            ), self.assertRaises(
                ValueError
            ):
                health.check()
