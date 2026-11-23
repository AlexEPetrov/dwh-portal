"""Portable deployment and release checks; Docker is always fake or mocked."""

import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "infra/images/portal-harness"
spec = importlib.util.spec_from_file_location(
    "package_release", ROOT / "infra/scripts/package_release.py"
)
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)
with patch.dict(sys.modules, {"package_release": release}):
    build_spec = importlib.util.spec_from_file_location(
        "build_release", ROOT / "infra/scripts/build_release.py"
    )
    builder = importlib.util.module_from_spec(build_spec)
    build_spec.loader.exec_module(builder)


class PortableLauncherTests(unittest.TestCase):
    def test_dsh_portable_lifecycle_defaults_errors_and_failure_propagation(self):
        for staged in (False, True):
            with self.subTest(
                staged=staged
            ), tempfile.TemporaryDirectory() as temporary:
                work = Path(temporary)
                scripts = ROOT / "infra/environments/dsh"
                if staged:
                    destination = work / "release"
                    destination.mkdir()
                    for name in ("compose.sh", "up.sh", "down.sh"):
                        shutil.copy2(scripts / name, destination / name)
                    (destination / "docker-compose-dsh.yml").write_text("{}\n")
                    scripts = destination
                capture = work / "arguments"
                marker = work / "must-not-run"
                env_file = work / "private settings.env"
                env_file.write_text(f'UNTRUSTED=$(touch "{marker}")\n')
                fake = work / "docker"
                fake.write_text(
                    '#!/bin/sh\nprintf "%s\\n" "$@" > "$CAPTURE_PATH"\nexit 4\n'
                )
                fake.chmod(0o700)
                environment = {
                    "PATH": f"{work}:{os.defpath}",
                    "CAPTURE_PATH": str(capture),
                }
                for action in ("up", "down"):
                    result = subprocess.run(
                        ["bash", str(scripts / f"{action}.sh"), env_file.name],
                        cwd=work,
                        env=environment,
                        capture_output=True,
                    )
                    self.assertEqual(result.returncode, 4)
                    self.assertFalse(marker.exists())
                    args = capture.read_text().splitlines()
                    self.assertEqual(
                        args[:5],
                        [
                            "compose",
                            "--project-name",
                            "dwh-dsh",
                            "--env-file",
                            str(env_file),
                        ],
                    )
                    self.assertEqual(
                        Path(args[6]).resolve(),
                        (
                            scripts / "docker-compose-dsh.yml"
                            if staged
                            else ROOT / "infra/compose/docker-compose-dsh.yml"
                        ),
                    )
                    self.assertEqual(
                        args[7:], ["up", "-d"] if action == "up" else ["down"]
                    )
                    capture.unlink()
                for extra in (["missing.env"], [str(env_file), "extra.env"]):
                    result = subprocess.run(
                        ["bash", str(scripts / "up.sh"), *extra],
                        cwd=work,
                        env=environment,
                        capture_output=True,
                    )
                    self.assertEqual(result.returncode, 2)
                    self.assertFalse(capture.exists())
                if staged:
                    (scripts / ".env").write_text("# private fixture\n")
                    subprocess.run(
                        ["bash", str(scripts / "up.sh")],
                        cwd=work,
                        env=environment,
                        capture_output=True,
                    )
                    self.assertIn(
                        str(scripts / ".env"), capture.read_text().splitlines()
                    )

    def test_db_diagnostic_is_portable_independent_and_propagates_failure(self):
        for staged in (False, True):
            with self.subTest(
                staged=staged
            ), tempfile.TemporaryDirectory() as temporary:
                work = Path(temporary)
                scripts = ROOT / "infra/environments/portal-harness"
                if staged:
                    destination = work / "release"
                    destination.mkdir()
                    for name in ("compose.sh", "diagnose-db.sh"):
                        shutil.copy2(scripts / name, destination / name)
                    (destination / "docker-compose-portal-harness.yml").write_text(
                        "{}\n"
                    )
                    scripts = destination
                env_file = work / "private settings.env"
                marker = work / "must-not-run"
                env_file.write_text(f'UNTRUSTED=$(touch "{marker}")\n')
                capture = work / "arguments"
                fake = work / "docker"
                fake.write_text(
                    '#!/bin/sh\nprintf "%s\\n" "$@" > "$CAPTURE_PATH"\n'
                    'cat > "$CAPTURE_PATH.stdin"\nexit 4\n'
                )
                fake.chmod(0o700)
                result = subprocess.run(
                    ["bash", str(scripts / "diagnose-db.sh"), env_file.name],
                    cwd=work,
                    env={"PATH": f"{work}:{os.defpath}", "CAPTURE_PATH": str(capture)},
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(result.returncode, 4)
                self.assertEqual(result.stdout, "")
                self.assertEqual(result.stderr, "")
                self.assertFalse(marker.exists())
                args = capture.read_text().splitlines()
                self.assertEqual(
                    args[:5],
                    [
                        "compose",
                        "--project-name",
                        "dwh-portal-harness",
                        "--env-file",
                        str(env_file),
                    ],
                )
                compose = Path(args[6]).resolve()
                self.assertEqual(
                    compose.parent, scripts if staged else ROOT / "infra/compose"
                )
                self.assertEqual(
                    args[7:],
                    [
                        "--file",
                        "-",
                        "run",
                        "--rm",
                        "--no-deps",
                        "-T",
                        "--entrypoint",
                        "python3",
                        "portal-harness",
                        "/opt/portal/diagnose_db.py",
                    ],
                )
                self.assertEqual(
                    Path(str(capture) + ".stdin").read_text(),
                    "services:\n  portal-harness:\n    pull_policy: never\n",
                )
                self.assertNotIn("--pull", args)
                self.assertNotIn("--service-ports", args)
                capture.unlink()
                missing = subprocess.run(
                    ["bash", str(scripts / "diagnose-db.sh"), "missing.env"],
                    cwd=work,
                    env={"PATH": f"{work}:{os.defpath}", "CAPTURE_PATH": str(capture)},
                    capture_output=True,
                )
                self.assertEqual(missing.returncode, 2)
                self.assertFalse(capture.exists())

    def test_producer_and_target_payload_ownership_are_separate(self):
        environment = ROOT / "infra/environments/portal-harness"
        for name in (
            "up.sh",
            "down.sh",
            "compose.sh",
            "diagnose-db.sh",
            "sample.env",
            "README.md",
        ):
            self.assertTrue((environment / name).is_file())
        for name in ("build-release.sh", "run-demo.sh", "package_release.py"):
            self.assertFalse((environment / name).exists())
        self.assertFalse((SOURCE / "package_release.py").exists())
        for name in (
            "build_env_portal_harness.sh",
            "package_portal_harness_release.py",
            "run_portal_harness_demo.sh",
            "build_env_test.sh",
            "README.md",
        ):
            self.assertTrue((ROOT / "infra/scripts" / name).is_file())

    def test_test_build_entry_resolves_its_helper_from_any_working_directory(self):
        with tempfile.TemporaryDirectory() as temporary:
            work = Path(temporary)
            scripts = work / "infra/scripts"
            scripts.mkdir(parents=True)
            shutil.copy2(
                ROOT / "infra/scripts/build_env_test.sh", scripts / "build_env_test.sh"
            )
            # Capture only the compatibility profile dispatch.
            (scripts / "_build_target.sh").write_text(
                '#!/bin/bash\nprintf "%s\\n" "$CI_ENVIRONMENT" > "$CAPTURE_PATH"\n'
            )
            caller = work / "elsewhere"
            caller.mkdir()
            capture = work / "environment"
            subprocess.run(
                ["bash", str(scripts / "build_env_test.sh")],
                cwd=caller,
                env={"PATH": os.defpath, "CAPTURE_PATH": str(capture)},
                check=True,
            )
            self.assertEqual(capture.read_text(), "test\n")
        source = (ROOT / "infra/scripts/_build_target.sh").read_text()
        self.assertIn('"$DIRECTORY/build_release.py"', source)
        for forbidden in ("rm -rf", "find .", "npm", "docker", "cp "):
            self.assertNotIn(forbidden, source)

    def test_both_build_entries_use_shared_engine_and_defaults_from_another_cwd(
        self,
    ):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            scripts = root / "infra/scripts"
            scripts.mkdir(parents=True)
            for name in (
                "build_env_portal_harness.sh",
                "build_env_test.sh",
                "build_env_dsh.sh",
                "_build_target.sh",
                "build_release.py",
            ):
                shutil.copy2(ROOT / "infra/scripts" / name, scripts / name)
            marker = root / "image-build-called"
            for profile in ("test", "portal-harness", "dsh"):
                image_dir = root / "infra/images" / profile
                image_dir.mkdir(parents=True)
                (image_dir / "build.sh").write_text(
                    f'#!/bin/sh\nprintf built > "{marker}"\n'
                )
            # Exercise the real shared build engine; stub only its export boundary.
            (scripts / "package_release.py").write_text(
                "from pathlib import Path\n"
                "ROOT = Path(__file__).resolve().parents[2]\n"
                "PROFILES = {p: {'builder': f'infra/images/{p}/build.sh'} "
                "for p in ('test', 'portal-harness', 'dsh')}\n"
                "def require_new_output(p):\n"
                " if p.exists() or p.is_symlink(): raise ValueError('already exists')\n"
                "def package_release(p, profile, root):\n"
                " p.mkdir(parents=True)\n (p / 'stub-export').write_text(profile)\n"
            )
            caller = root / "elsewhere"
            caller.mkdir()
            env = {"PATH": f"{Path(sys.executable).parent}:{os.defpath}"}
            for profile, entry in (
                ("test", "build_env_test.sh"),
                ("portal-harness", "build_env_portal_harness.sh"),
                ("dsh", "build_env_dsh.sh"),
            ):
                command = ["bash", str(scripts / entry)]
                subprocess.run(command, cwd=caller, env=env, check=True)
                self.assertTrue(marker.is_file())
                self.assertEqual(
                    (root / f".build/{profile}/stub-export").read_text(), profile
                )
                marker.unlink()
                refused = subprocess.run(
                    command, cwd=caller, env=env, capture_output=True
                )
                self.assertEqual(refused.returncode, 2)
                self.assertFalse(marker.exists())
                subprocess.run(
                    command + ["custom " + profile], cwd=caller, env=env, check=True
                )
                self.assertTrue(
                    (caller / ("custom " + profile) / "stub-export").is_file()
                )
                marker.unlink()

    def test_up_down_work_in_checkout_and_self_contained_release_without_real_docker(
        self,
    ):
        for environment in ("portal-harness", "test"):
            for staged in (False, True):
                for action in ("up", "down"):
                    with self.subTest(
                        environment=environment, staged=staged, action=action
                    ):
                        with tempfile.TemporaryDirectory() as temporary:
                            work = Path(temporary)
                            scripts = ROOT / "infra/environments" / environment
                            if staged:
                                destination = work / environment
                                destination.mkdir()
                                for name in ("up.sh", "down.sh", "compose.sh"):
                                    shutil.copy2(scripts / name, destination / name)
                                scripts = destination
                                names = (
                                    ("docker-compose-portal-harness.yml",)
                                    if environment == "portal-harness"
                                    else (
                                        "docker-compose.yml",
                                        "docker-compose-dev.yml",
                                    )
                                )
                                for name in names:
                                    (destination / name).write_text("{}\n")
                            env_file = work / "settings with spaces.env"
                            env_file.write_text("# no real credentials\n")
                            fake = work / "docker"
                            fake.write_text(
                                '#!/bin/sh\nprintf "%s\\n" "$@" > "$CAPTURE_PATH"\n'
                                'printf "%s\\n" "$PORTAL_HARNESS_FRONTEND_DIST_HOST" > "$CAPTURE_PATH.frontend"\n'
                            )
                            fake.chmod(0o700)
                            capture = work / "arguments"
                            subprocess.run(
                                ["bash", str(scripts / f"{action}.sh"), str(env_file)],
                                cwd=work,
                                env={
                                    "PATH": f"{work}:{os.defpath}",
                                    "CAPTURE_PATH": str(capture),
                                },
                                check=True,
                                capture_output=True,
                                text=True,
                            )
                            args = capture.read_text().splitlines()
                            self.assertEqual(args[0], "compose")
                            self.assertEqual(
                                args[args.index("--env-file") + 1], str(env_file)
                            )
                            files = [
                                Path(args[i + 1]).resolve()
                                for i, arg in enumerate(args)
                                if arg == "--file"
                            ]
                            self.assertTrue(all(path.is_file() for path in files))
                            if staged:
                                self.assertTrue(
                                    all(path.parent == scripts for path in files)
                                )
                            else:
                                self.assertTrue(
                                    all(
                                        path.parent == ROOT / "infra/compose"
                                        for path in files
                                    )
                                )
                            if environment == "portal-harness":
                                frontend = (
                                    Path(str(capture) + ".frontend").read_text().strip()
                                )
                                self.assertEqual(
                                    Path(frontend).resolve(),
                                    (
                                        scripts / "frontend-dist"
                                        if staged
                                        else ROOT / "frontend/web/dist"
                                    ),
                                )
                                self.assertEqual(
                                    args[args.index("--project-name") + 1],
                                    "dwh-portal-harness",
                                )
                            else:
                                self.assertEqual(
                                    Path(args[args.index("--project-directory") + 1]),
                                    scripts,
                                )
                                self.assertEqual(len(files), 2 if staged else 3)
                            self.assertEqual(
                                (
                                    args[-2:]
                                    if environment == "portal-harness"
                                    and action == "up"
                                    else args[-1:]
                                ),
                                (
                                    ["up", "-d"]
                                    if environment == "portal-harness"
                                    and action == "up"
                                    else [action]
                                ),
                            )
                            self.assertNotIn("--volumes", args)
                            self.assertNotIn("--rmi", args)
                            self.assertNotIn("--remove-orphans", args)

    def test_image_helpers_build_shared_base_before_extension_from_any_cwd(self):
        with tempfile.TemporaryDirectory() as temporary:
            work = Path(temporary)
            capture = work / "arguments"
            fake = work / "docker"
            fake.write_text(
                '#!/bin/sh\nprintf "%s\\n" "$@" >> "$CAPTURE_PATH"\n'
                'printf "END\\n" >> "$CAPTURE_PATH"\n'
            )
            fake.chmod(0o700)
            environment = {"PATH": f"{work}:{os.defpath}", "CAPTURE_PATH": str(capture)}
            for helper, expected in (
                (
                    ROOT / "infra/images/portal-harness/build.sh",
                    [
                        "infra/images/portal/Dockerfile",
                        "infra/images/portal-harness/Dockerfile",
                    ],
                ),
                (
                    ROOT / "backend/core-service/build_image.sh",
                    ["infra/images/portal/Dockerfile"],
                ),
            ):
                if capture.exists():
                    capture.unlink()
                subprocess.run(
                    ["sh", str(helper)], cwd=work, env=environment, check=True
                )
                calls = [
                    c.splitlines() for c in capture.read_text().split("END\n") if c
                ]
                self.assertEqual(len(calls), len(expected))
                self.assertEqual([c[c.index("--file") + 1] for c in calls], expected)
                self.assertTrue(all(c[0] == "build" and c[-1] == "." for c in calls))
                self.assertEqual(
                    calls[0][calls[0].index("--tag") + 1], release.BASE_IMAGE
                )


class ReleaseTests(unittest.TestCase):
    def test_dsh_release_reuses_combined_image_without_portal_payload_or_container(
        self,
    ):
        config = release.PROFILES["dsh"]
        self.assertEqual(config["image"], release.PROFILES["portal-harness"]["image"])
        self.assertEqual(
            config["builder"], release.PROFILES["portal-harness"]["builder"]
        )
        for fail in (False, True):
            with self.subTest(fail=fail), tempfile.TemporaryDirectory() as temporary:
                destination = Path(temporary) / "release"
                calls = []

                def run(args, **kwargs):
                    calls.append(args)
                    self.assertEqual(args[:2], ["docker", "save"])
                    if fail:
                        raise subprocess.CalledProcessError(4, args)
                    Path(args[args.index("--output") + 1]).write_bytes(
                        b"fake shared image"
                    )

                with patch.object(
                    release.subprocess,
                    "check_output",
                    side_effect=["sha256:shared\n", "commit\n", ""],
                ), patch.object(release.subprocess, "run", side_effect=run):
                    if fail:
                        with self.assertRaises(subprocess.CalledProcessError):
                            release.package_release(destination, "dsh")
                    else:
                        release.package_release(destination, "dsh")
                self.assertEqual(len(calls), 1)
                self.assertEqual((destination / "RELEASE_FAILED").exists(), fail)
                self.assertEqual((destination / "RELEASE_COMPLETE").exists(), not fail)
                for name in (
                    "migrations",
                    "frontend-dist",
                    "src",
                    "diagnose-db.sh",
                    ".env",
                ):
                    self.assertFalse((destination / name).exists())
                if not fail:
                    expected = {
                        *config["payload"],
                        *config["compose"],
                        config["archive"],
                        "release.json",
                        "commit-sh.txt",
                        "SHA256SUMS",
                        "RELEASE_COMPLETE",
                    }
                    self.assertEqual(
                        {path.name for path in destination.iterdir()}, expected
                    )
                    metadata = json.loads((destination / "release.json").read_text())
                    self.assertEqual(metadata["profile"], "dsh")
                    self.assertIn("dsh", metadata)
                    for name in ("up.sh", "down.sh", "compose.sh"):
                        self.assertTrue(os.access(destination / name, os.X_OK))
                    for line in (destination / "SHA256SUMS").read_text().splitlines():
                        digest, name = line.split("  ", 1)
                        self.assertEqual(
                            digest,
                            hashlib.sha256(
                                (destination / name).read_bytes()
                            ).hexdigest(),
                        )
                with patch.object(builder.subprocess, "run") as build:
                    with self.assertRaises(ValueError):
                        builder.build_release("dsh", destination)
                    build.assert_not_called()

    def test_harness_compatibility_exporter_delegates_to_shared_engine(self):
        compatibility_spec = importlib.util.spec_from_file_location(
            "package_portal_harness_release",
            ROOT / "infra/scripts/package_portal_harness_release.py",
        )
        compatibility = importlib.util.module_from_spec(compatibility_spec)
        with patch.dict(sys.modules, {"package_release": release}):
            compatibility_spec.loader.exec_module(compatibility)
        with patch.object(compatibility, "export_release") as export:
            output = Path("not-created-by-test")
            compatibility.package_release(output)
            export.assert_called_once_with(output, "portal-harness")

    def test_export_collects_image_and_runtime_files_without_real_env_or_container_start(
        self,
    ):
        commands = []

        def output(args, **kwargs):
            if args[:3] == ["docker", "image", "inspect"]:
                return "sha256:test-image\n"
            if args == ["git", "rev-parse", "HEAD"]:
                return "test-commit\n"
            return " M authoring-source\n"

        def run(args, **kwargs):
            commands.append(args)
            if args[:2] == ["docker", "cp"]:
                destination = Path(args[-1])
                if args[-2].endswith("all.sql"):
                    destination.write_text("-- offline SQL artifact\n")
                else:
                    destination.mkdir()
                    (destination / "index.html").write_text("image frontend")
            elif args[:2] == ["docker", "save"]:
                Path(args[args.index("--output") + 1]).write_bytes(
                    b"fake image archive"
                )

        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "release"
            with patch.object(
                release.subprocess, "check_output", side_effect=output
            ), patch.object(release.subprocess, "run", side_effect=run):
                release.package_release(destination, "portal-harness")
            self.assertTrue((destination / "RELEASE_COMPLETE").is_file())
            self.assertTrue((destination / "dwh-portal-dsh.img").is_file())
            self.assertTrue((destination / "migrations/all.sql").is_file())
            self.assertEqual(
                (destination / "frontend-dist/index.html").read_text(), "image frontend"
            )
            self.assertTrue(
                (destination / "docker-compose-portal-harness.yml").is_file()
            )
            for name in (
                "up.sh",
                "down.sh",
                "compose.sh",
                "diagnose-db.sh",
            ):
                self.assertTrue(os.access(destination / name, os.X_OK))
            self.assertFalse((destination / ".env").exists())
            self.assertFalse((destination / "run-sql.sh").exists())
            self.assertFalse((destination / "build_env_portal_harness.sh").exists())
            self.assertFalse(
                (destination / "package_portal_harness_release.py").exists()
            )
            self.assertTrue(
                json.loads((destination / "release.json").read_text())[
                    "working_tree_dirty"
                ]
            )
            self.assertTrue((destination / "SHA256SUMS").read_text())
            self.assertFalse(
                any(
                    command[:2] in (["docker", "run"], ["docker", "start"])
                    for command in commands
                )
            )
            self.assertEqual(
                sum(command[:2] == ["docker", "rm"] for command in commands), 1
            )

    def test_export_refuses_existing_output_before_docker(self):
        with tempfile.TemporaryDirectory() as temporary, patch.object(
            release.subprocess, "check_output"
        ) as docker:
            with self.assertRaises(ValueError):
                release.package_release(Path(temporary), "portal-harness")
            docker.assert_not_called()

    def test_export_failure_preserves_partial_artifacts_and_removes_owned_container(
        self,
    ):
        commands = []

        def run(args, **kwargs):
            commands.append(args)
            if args[:2] == ["docker", "cp"]:
                raise subprocess.CalledProcessError(1, args)

        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "release"
            with patch.object(
                release.subprocess, "check_output", return_value="test\n"
            ), patch.object(release.subprocess, "run", side_effect=run):
                with self.assertRaises(subprocess.CalledProcessError):
                    release.package_release(destination, "portal-harness")
            self.assertTrue((destination / "RELEASE_FAILED").is_file())
            self.assertFalse((destination / "RELEASE_COMPLETE").exists())
            self.assertTrue((destination / "up.sh").is_file())
            self.assertEqual(commands[-1][:2], ["docker", "rm"])

    def test_both_profiles_export_only_allowlisted_payload_and_image_derived_artifacts(
        self,
    ):
        for profile, config in release.PROFILES.items():
            commands = []

            def run(args, **kwargs):
                commands.append(args)
                if args[:2] == ["docker", "cp"]:
                    destination = Path(args[-1])
                    if args[-2].endswith("all.sql"):
                        destination.write_text("-- offline SQL\n")
                    else:
                        destination.mkdir()
                        (destination / "from-image").write_text("image contents")
                if args[:2] == ["docker", "save"]:
                    Path(args[args.index("--output") + 1]).write_bytes(b"image")

            with self.subTest(
                profile=profile
            ), tempfile.TemporaryDirectory() as temporary:
                output = Path(temporary) / profile
                with patch.object(
                    release.subprocess, "check_output", return_value="identity\n"
                ), patch.object(release.subprocess, "run", side_effect=run):
                    release.package_release(output, profile)
                expected = (
                    set(config["payload"])
                    | set(config["compose"])
                    | set(config["image_paths"])
                    | {
                        config["archive"],
                        "commit-sh.txt",
                        "release.json",
                        "SHA256SUMS",
                        "RELEASE_COMPLETE",
                    }
                )
                if profile != "dsh":
                    expected.add("migrations")
                self.assertEqual({p.name for p in output.iterdir()}, expected)
                self.assertFalse((output / ".env").exists())
                metadata = json.loads((output / "release.json").read_text())
                self.assertEqual(metadata["profile"], profile)
                self.assertEqual(
                    "dsh" in metadata, profile in {"portal-harness", "dsh"}
                )
                if profile != "dsh":
                    create = next(c for c in commands if c[:2] == ["docker", "create"])
                    self.assertEqual(create[2:4], ["--network", "none"])
                    self.assertEqual(create[-1], "identity")
                    remove = next(c for c in commands if c[:2] == ["docker", "rm"])
                    self.assertEqual(remove[2], create[5])
                else:
                    self.assertEqual([c[1] for c in commands], ["save"])
                self.assertFalse(
                    any(c[1] in ("start", "run", "exec") for c in commands)
                )
                for line in (output / "SHA256SUMS").read_text().splitlines():
                    digest, path = line.split("  ", 1)
                    self.assertEqual(
                        hashlib.sha256((output / path).read_bytes()).hexdigest(), digest
                    )
                for name in config["image_paths"]:
                    self.assertTrue((output / name / "from-image").is_file())

    def test_build_pipeline_uses_each_registered_image_helper_and_common_exporter(self):
        for profile, config in release.PROFILES.items():
            with tempfile.TemporaryDirectory() as temporary, patch.object(
                builder.subprocess, "run"
            ) as run, patch.object(builder, "package_release") as export:
                output = Path(temporary) / "new"
                builder.build_release(profile, output)
                run.assert_called_once_with(
                    ["sh", str(ROOT / config["builder"])], cwd=ROOT, check=True
                )
                export.assert_called_once_with(output, profile, ROOT)

    def test_build_failure_never_exports(self):
        with tempfile.TemporaryDirectory() as temporary, patch.object(
            builder.subprocess,
            "run",
            side_effect=subprocess.CalledProcessError(1, "stub"),
        ), patch.object(builder, "package_release") as export:
            with self.assertRaises(subprocess.CalledProcessError):
                builder.build_release("test", Path(temporary) / "new")
            export.assert_not_called()

    def test_existing_and_dangling_symlink_outputs_are_refused_before_any_build(self):
        for profile in release.PROFILES:
            with tempfile.TemporaryDirectory() as temporary, patch.object(
                builder.subprocess, "run"
            ) as run:
                directory = Path(temporary)
                sentinel = directory / "sentinel"
                sentinel.write_text("preserved")
                link = directory / "dangling"
                link.symlink_to(directory / "missing")
                for output in (directory, sentinel, link):
                    with self.assertRaises(ValueError):
                        builder.build_release(profile, output)
                run.assert_not_called()
                self.assertEqual(sentinel.read_text(), "preserved")
                self.assertTrue(link.is_symlink())

    def test_all_producer_python_sources_parse_without_bytecode(self):
        for name in (
            "package_release.py",
            "build_release.py",
            "package_portal_harness_release.py",
        ):
            path = ROOT / "infra/scripts" / name
            compile(path.read_text(), str(path), "exec")
