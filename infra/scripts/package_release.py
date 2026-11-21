"""Shared profile-driven export of built Portal images; never start containers."""

import hashlib
import json
import os
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE_IMAGE = "134/dwh-portal-core-service:1.2"
PROFILES = {
    "test": {
        "image": BASE_IMAGE,
        "builder": "infra/images/portal/build.sh",
        "archive": "dwh-portal-core-service.img",
        "payload": ("up.sh", "down.sh", "compose.sh", "sample.env", "README.md"),
        "compose": ("docker-compose.yml", "docker-compose-dev.yml"),
        "image_paths": ("src", "frontend-dist"),
    },
    "portal-harness": {
        "image": "134/dwh-portal-dsh:0.2.2-rc.5-source-experimental",
        "builder": "infra/images/portal-harness/build.sh",
        "archive": "dwh-portal-dsh.img",
        "payload": (
            "up.sh",
            "down.sh",
            "compose.sh",
            "run-sql.sh",
            "diagnose-db.sh",
            "sample.env",
            "README.md",
        ),
        "compose": ("docker-compose-portal-harness.yml",),
        "image_paths": (),
    },
}


def require_new_output(output: Path) -> None:
    """Refuse existing/partial artifacts and dangling symlinks without removing them."""
    if output.exists() or output.is_symlink():
        raise ValueError("Release output already exists; choose a new directory")


def package_release(output: Path, profile: str, root: Path = ROOT) -> None:
    """Create a new self-contained release directory without overwriting user state."""
    output = output.absolute()
    config = PROFILES[profile]
    image = config["image"]
    require_new_output(output)
    image_id = subprocess.check_output(
        ["docker", "image", "inspect", image, "--format", "{{.Id}}"], text=True
    ).strip()
    commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=root, text=True
    ).strip()
    dirty = bool(
        subprocess.check_output(["git", "status", "--porcelain"], cwd=root, text=True)
    )
    output.mkdir(parents=True, exist_ok=False)
    environment = root / "infra/environments" / profile
    try:
        for name in config["payload"]:
            shutil.copy2(environment / name, output / name)
            if name.endswith(".sh"):
                (output / name).chmod((output / name).stat().st_mode | 0o111)
        for name in config["compose"]:
            shutil.copy2(root / "infra/compose" / name, output / name)
        output.joinpath("migrations").mkdir()
        container = f"portal-release-{uuid.uuid4().hex}"
        subprocess.run(
            ["docker", "create", "--network", "none", "--name", container, image_id],
            check=True,
        )
        try:
            subprocess.run(
                [
                    "docker",
                    "cp",
                    f"{container}:/app/migrations/all.sql",
                    os.fspath(output / "migrations/all.sql"),
                ],
                check=True,
            )
            # Test Compose bind mounts remain functional after transfer. Both
            # trees come from the SAME image, never stale host build output.
            for name in config["image_paths"]:
                subprocess.run(
                    [
                        "docker",
                        "cp",
                        f"{container}:/app/{name}",
                        os.fspath(output / name),
                    ],
                    check=True,
                )
        finally:
            # Only this packaging operation's never-started temporary container.
            subprocess.run(["docker", "rm", container], check=True)
        subprocess.run(
            [
                "docker",
                "save",
                "--output",
                os.fspath(output / config["archive"]),
                image,
            ],
            check=True,
        )
        metadata = {
            "profile": profile,
            "image": image,
            "image_id": image_id,
            "portal_base_image": BASE_IMAGE,
            "commit": commit,
            "working_tree_dirty": dirty,
        }
        if profile == "portal-harness":
            metadata["dsh"] = json.loads(
                (root / "infra/images/portal-harness/dsh-source.json").read_text()
            )
        (output / "commit-sh.txt").write_text(commit + "\n")
        (output / "release.json").write_text(json.dumps(metadata, indent=2) + "\n")
        # Include the image in checksums without loading its potentially large bytes at once.
        checksums = []
        for path in sorted(output.rglob("*")):
            if path.is_file():
                digest = hashlib.sha256()
                with path.open("rb") as source:
                    for chunk in iter(lambda: source.read(1024 * 1024), b""):
                        digest.update(chunk)
                checksums.append(f"{digest.hexdigest()}  {path.relative_to(output)}\n")
        (output / "SHA256SUMS").write_text("".join(checksums))
        (output / "RELEASE_COMPLETE").write_text(
            "Release export completed; no deployment or migrations were run.\n"
        )
    except Exception:
        # Preserve partial evidence rather than deleting/overwriting an output directory.
        (output / "RELEASE_FAILED").write_text(
            "Release export failed; do not deploy this directory.\n"
        )
        raise


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] not in PROFILES:
        raise SystemExit(
            "Usage: package_release.py <test|portal-harness> <new-output-directory>"
        )
    package_release(Path(sys.argv[2]), sys.argv[1])
