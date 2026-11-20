"""Dependency-free checks of source-pinned DSH packaging and supervision."""

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

SOURCE = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name, SOURCE / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


launcher = load("launch")
smoke = load("container_smoke")
with patch.dict(sys.modules, {"launch": launcher}):
    cli_check = load("check_dsh_cli")


class ConfigurationTests(unittest.TestCase):
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
        guard = (SOURCE / "dsh-guard.mjs").read_text()
        self.assertIn("ctx.tools.guard(() =>", guard)
        self.assertIn("portal-harness-guard-ready", guard)

    def test_build_excludes_local_secrets_and_dependencies(self):
        ignored = (SOURCE / "Dockerfile.dockerignore").read_text().splitlines()
        self.assertIn("**/.env", ignored)
        self.assertIn("**/.env.*", ignored)
        self.assertIn("**/node_modules", ignored)
        self.assertIn("**/.venv", ignored)
        dockerfile = (SOURCE / "Dockerfile").read_text()
        self.assertIn("USER 1001:0", dockerfile)
        self.assertIn("134/python-builder-313:1.0", dockerfile)
        self.assertIn("134/python-slim-313:1.0", dockerfile)
        self.assertIn("COPY common/contracts/jsonschema/", dockerfile)
        self.assertIn("dsh --version", dockerfile)
        self.assertIn("COPY --from=harness /usr/local/bin/node", dockerfile)
        self.assertNotIn("opencode", dockerfile.lower())

    def test_every_python_source_parses_without_writing_bytecode(self):
        for path in SOURCE.rglob("*.py"):
            with self.subTest(path=path.name):
                compile(path.read_text(), str(path), "exec")


class LauncherTests(unittest.TestCase):
    def test_harness_environment_excludes_portal_credentials(self):
        environment = launcher.harness_environment(
            {
                "PATH": "/bin",
                "APP_DB_PSG_PASS": "database-secret",
                "APP_AUTH_SESSION_SECRET_KEY": "session-secret",
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
        self.assertNotIn("UNRELATED_SECRET", environment)
        self.assertNotIn("PYTHONPATH", environment)
        self.assertNotIn("DSH_EXTRA_FLAGS", environment)
        self.assertNotIn("NODE_OPTIONS", environment)
        self.assertEqual(environment["HOME"], "/var/lib/dsh")
        self.assertEqual(environment["DSH_HOME"], "/var/lib/dsh")

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
