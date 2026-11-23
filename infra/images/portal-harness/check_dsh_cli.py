"""Build-time validation using exactly the launcher's DSH argument vector."""

import json
import os
import subprocess
from pathlib import Path

from launch import commands


def check():
    environment = dict(os.environ)
    environment["DSH_BIND_HOST"] = "127.0.0.1"
    # Offline argv validation uses the combined-mode local MCP default; no remote
    # deployment endpoint is invented or contacted during image construction.
    specification = commands("all", environment)[-1]
    Path(specification["cwd"]).mkdir(parents=True, exist_ok=True)
    options = {
        "cwd": specification["cwd"],
        "env": specification["env"],
        "check": True,
        "timeout": 60,
    }
    subprocess.run(
        [
            "/usr/local/bin/node",
            "/opt/portal-harness/check_dsh_cli.mjs",
            json.dumps(specification["args"][1:]),
        ],
        **options,
    )
    subprocess.run([*specification["args"], "--help"], **options)


if __name__ == "__main__":
    check()
