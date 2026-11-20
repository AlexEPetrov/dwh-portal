"""Check selected local services without credentials, models or proxy routing."""

import json
import os
import sys
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import ProxyHandler, build_opener


def check():
    state = json.loads(Path("/tmp/portal-harness-mode").read_text())
    if state["mode"] not in {"all", "portal", "harness"}:
        raise ValueError("Unknown launcher state")
    opener = build_opener(ProxyHandler({}))
    if state["mode"] in {"all", "portal"}:
        with opener.open(
            f"http://127.0.0.1:{os.environ.get('APP_API_PORT', '5051')}/health",
            timeout=3,
        ) as response:
            if response.status != 200:
                raise ValueError("Portal is not healthy")
    if state["mode"] in {"all", "harness"}:
        if Path("/tmp/portal-harness-guard-ready").read_text().strip() != str(
            state["pid"]
        ):
            raise ValueError("DSH tool guard is not active")
        # The index is protected. A 401 proves the listener/auth fence is up;
        # the separate smoke check exercises token exchange and bundled HTML.
        try:
            with opener.open(f"http://{state['host']}:{state['port']}/", timeout=3):
                raise ValueError("DSH accepted an unauthenticated index request")
        except HTTPError as error:
            if error.code != 401:
                raise ValueError("Unexpected DSH authentication response") from None


if __name__ == "__main__":
    try:
        check()
    except Exception as error:
        print(f"Health check failed: {type(error).__name__}", file=sys.stderr)
        sys.exit(1)
