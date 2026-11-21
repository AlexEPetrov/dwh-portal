"""Compatibility entry point; all release behavior lives in package_release."""

import sys
from pathlib import Path

from package_release import package_release as export_release


def package_release(output: Path) -> None:
    """Export the harness through the same engine as the Portal test profile."""
    export_release(output, "portal-harness")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(
            "Usage: package_portal_harness_release.py <new-output-directory>"
        )
    package_release(Path(sys.argv[1]))
