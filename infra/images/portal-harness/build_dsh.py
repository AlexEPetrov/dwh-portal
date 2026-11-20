"""Build the pinned DSH checkout; this script runs only in the image builder."""

import json
import subprocess
from pathlib import Path


def run(*args, cwd=None):
    subprocess.run(args, cwd=cwd, check=True)


def main():
    """Retain the upstream lockfile, build pipeline and runtime deploy policy."""
    manifest = json.loads(Path(__file__).with_name("dsh-source.json").read_text())
    source = Path("/build/dsh-source")
    source.mkdir()
    run("git", "init", str(source))
    run("git", "remote", "add", "origin", manifest["repository"], cwd=source)
    run("git", "fetch", "--depth=1", "origin", manifest["commit"], cwd=source)
    run("git", "checkout", "--detach", "FETCH_HEAD", cwd=source)
    actual = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=source, text=True
    ).strip()
    if actual != manifest["commit"]:
        raise ValueError("DSH source commit mismatch")
    package = json.loads((source / "package.json").read_text())
    if (
        package["version"] != manifest["version"]
        or package["packageManager"] != f"pnpm@{manifest['pnpm']}"
    ):
        raise ValueError("DSH source version or package-manager pin mismatch")
    run("npm", "install", "--global", f"pnpm@{manifest['pnpm']}")
    run("pnpm", "install", "--frozen-lockfile", cwd=source)
    run("pnpm", "run", "build:official", cwd=source)
    run("pnpm", "run", "verify-runtime-closure", cwd=source)
    # Same closure and deployment options used by upstream's Node carrier.
    run(
        "pnpm",
        "--filter",
        "dsh-python-runtime-closure",
        "deploy",
        "--prod",
        "--config.allow-unused-patches=true",
        "--config.node-linker=hoisted",
        f"--config.pnpmfile={source}/scripts/python-runtime-deploy.pnpmfile.mjs",
        "--config.link-workspace-packages=true",
        "--config.hoist-workspace-packages=false",
        "/opt/dsh",
        cwd=source,
    )
    run("pnpm", "exec", "tsx", "/build/materialize_dsh.mts", cwd=source)
    # Preserve build provenance and the actual upstream dependency lock.
    Path("/opt/dsh/upstream-pnpm-lock.yaml").write_bytes(
        (source / "pnpm-lock.yaml").read_bytes()
    )
    Path("/opt/dsh/LICENSE").write_bytes((source / "LICENSE").read_bytes())


if __name__ == "__main__":
    main()
