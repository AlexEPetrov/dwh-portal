"""One local/CI build-and-export pipeline, with explicit Portal release profiles."""

import argparse
import subprocess
from pathlib import Path

from package_release import PROFILES, ROOT, package_release, require_new_output


def build_release(profile: str, output: Path, root: Path = ROOT) -> None:
    """Build a profile's image then export safely, without touching old artifacts."""
    config = PROFILES[profile]
    # Refuse before any build as well as at the atomic output-directory creation.
    require_new_output(output)
    subprocess.run(["sh", str(root / config["builder"])], cwd=root, check=True)
    package_release(output, profile, root)


def main() -> None:
    """Resolve defaults identically for CI and local callers from any cwd."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("profile", choices=PROFILES)
    parser.add_argument("output", nargs="?", type=Path)
    args = parser.parse_args()
    output = args.output if args.output is not None else ROOT / ".build" / args.profile
    try:
        build_release(args.profile, output.absolute())
    except ValueError as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
