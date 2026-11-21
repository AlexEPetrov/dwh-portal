"""Check selected local services without credentials, models or proxy routing."""

import json
import os
import sys
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import ProxyHandler, build_opener


class CatalogReadinessError(ValueError):
    """A safe diagnostic for actual host catalog registration, not model inference."""


def check_catalog_registration(pid):
    """Require all four tools in this DSH process, without making another MCP client."""
    expected = {
        "mcp__portal__search_catalog",
        "mcp__portal__get_object",
        "mcp__portal__get_lineage",
        "mcp__portal__get_object_links",
    }
    try:
        status = json.loads(Path("/tmp/portal-harness-catalog-status.json").read_text())
        if status["version"] != 1 or status["pid"] != pid:
            raise ValueError("Stale status")
        registered = status["global"]
        if (
            registered["state"] != "ready"
            or set(registered["available"]) != expected
            or registered["missing"] != []
        ):
            raise ValueError("Incomplete registration")
    except (OSError, ValueError, KeyError, TypeError):
        raise CatalogReadinessError(
            "DSH catalog tools are unregistered, incomplete or unknown; "
            "guard/process readiness is not catalog readiness"
        ) from None


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
        check_catalog_registration(state["pid"])
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
        detail = (
            str(error)
            if isinstance(error, CatalogReadinessError)
            else type(error).__name__
        )
        print(f"Health check failed: {detail}", file=sys.stderr)
        sys.exit(1)
