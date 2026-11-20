"""Run Portal and/or source-built DSH with fail-fast supervision."""

import argparse
import ipaddress
import json
import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

STATE_FILE = Path("/tmp/portal-harness-mode")
WORKSPACE = Path("/var/lib/dsh/workspace")
GUARD_FILE = Path("/tmp/portal-harness-guard-ready")
PROVIDER_PREFIXES = (
    "OPENAI_",
    "ANTHROPIC_",
    "DEEPSEEK_",
    "GOOGLE_",
    "GEMINI_",
    "OLLAMA_",
)
SHARED_ENV = {
    "PATH",
    "LANG",
    "LC_ALL",
    "TZ",
    "SSL_CERT_FILE",
    "SSL_CERT_DIR",
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "NO_PROXY",
    "http_proxy",
    "https_proxy",
    "no_proxy",
}


def harness_environment(environment: dict[str, str]) -> dict[str, str]:
    """Avoid passing Portal/database secrets to the harness child process."""
    result = {
        key: value
        for key, value in environment.items()
        if key in SHARED_ENV or key.startswith(PROVIDER_PREFIXES)
    }
    result.update(
        {
            "HOME": "/var/lib/dsh",
            "DSH_HOME": "/var/lib/dsh",
            "DSH_AGENTS_HOME": "/var/lib/dsh/agents",
            "DSH_TELEMETRY_DISABLED": "1",
        }
    )
    return result


def port(value: str) -> int:
    """Reject invalid listen ports before either child starts."""
    number = int(value)
    if not 1024 <= number <= 65535:
        raise ValueError("Listen ports must be between 1024 and 65535")
    return number


def bind_host(environment: dict[str, str]) -> str:
    """Choose one concrete IPv4 interface, as required by DSH's trust fence."""
    explicit = environment.get("DSH_BIND_HOST")
    if explicit:
        address = ipaddress.IPv4Address(explicit)
        if address.is_unspecified or address.is_multicast:
            raise ValueError("DSH_BIND_HOST must be a concrete unicast IPv4 address")
        return str(address)
    addresses = {
        item[4][0]
        for item in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET)
        if not (
            ipaddress.IPv4Address(item[4][0]).is_loopback
            or ipaddress.IPv4Address(item[4][0]).is_unspecified
            or ipaddress.IPv4Address(item[4][0]).is_multicast
        )
    }
    if len(addresses) != 1:
        raise ValueError("Set DSH_BIND_HOST to one concrete container IPv4 address")
    return addresses.pop()


def commands(mode: str, environment: dict[str, str]) -> list[dict]:
    """Validate configuration and describe independently configured children."""
    children = []
    if mode in {"all", "portal"}:
        api_port = port(environment.get("APP_API_PORT", "5051"))
        portal_env = {
            key: value
            for key, value in environment.items()
            if not key.startswith(("DSH_", *PROVIDER_PREFIXES))
        }
        portal_env["APP_API_PORT"] = str(api_port)
        children.append(
            {
                "args": [sys.executable, "/app/src/api/run.py"],
                "cwd": "/app",
                "env": portal_env,
            }
        )
    if mode in {"all", "harness"}:
        harness_port = port(environment.get("DSH_PORT", "3080"))
        if mode == "all" and harness_port == api_port:
            raise ValueError("Portal and DSH must use different ports")
        host = bind_host(environment)
        public_url = environment.get(
            "DSH_PUBLIC_URL", f"http://127.0.0.1:{harness_port}/"
        )
        from urllib.parse import urlsplit

        public = urlsplit(public_url)
        if (
            public.scheme not in {"http", "https"}
            or not public.hostname
            or public.username
            or public.password
            or public.query
            or public.fragment
        ):
            raise ValueError(
                "DSH_PUBLIC_URL must be an HTTP(S) root without credentials or query"
            )
        children.append(
            {
                "args": [
                    "/usr/local/bin/dsh",
                    "--profile",
                    "web",
                    # DSH stops parsing launcher flags at the first app flag.
                    "--patch",
                    "/opt/portal-harness/dsh.patch.yml",
                    "--no-open",
                    "--host",
                    host,
                    "--port",
                    str(harness_port),
                    "--public-url",
                    public_url,
                    "--trusted-host",
                    public.netloc,
                ],
                "cwd": os.fspath(WORKSPACE),
                "env": harness_environment(environment),
            }
        )
    return children


def stop_children(children: list[subprocess.Popen]) -> None:
    """Stop process groups, allow graceful shutdown, then reap direct children."""
    for child in children:
        try:
            os.killpg(child.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    deadline = time.monotonic() + 10
    for child in children:
        try:
            child.wait(timeout=max(0.01, deadline - time.monotonic()))
        except subprocess.TimeoutExpired:
            pass
    # Also terminate grandchildren if their direct parent has already exited.
    for child in children:
        try:
            os.killpg(child.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        child.wait()


def main() -> int:
    """Exit the container when either required service stops or a signal arrives."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "mode", choices=("all", "portal", "harness"), nargs="?", default="all"
    )
    args = parser.parse_args()
    try:
        specifications = commands(args.mode, dict(os.environ))
    except (ValueError, OSError) as error:
        print(str(error), file=sys.stderr, flush=True)
        return 2
    if args.mode in {"all", "harness"}:
        WORKSPACE.mkdir(parents=True, exist_ok=True)
        GUARD_FILE.unlink(missing_ok=True)
    state = {"mode": args.mode}
    if args.mode in {"all", "harness"}:
        harness_args = specifications[-1]["args"]
        state["host"] = harness_args[harness_args.index("--host") + 1]
        state["port"] = harness_args[harness_args.index("--port") + 1]
    STATE_FILE.write_text(json.dumps(state))
    stopping = False

    def request_stop(_signum, _frame):
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)
    children = []
    try:
        for specification in specifications:
            if stopping:
                return 0
            children.append(subprocess.Popen(**specification, start_new_session=True))
        if args.mode in {"all", "harness"}:
            state["pid"] = children[-1].pid
            STATE_FILE.write_text(json.dumps(state))
        guard_deadline = time.monotonic() + 60
        while not stopping:
            if "pid" in state and time.monotonic() > guard_deadline:
                if not GUARD_FILE.exists() or GUARD_FILE.read_text().strip() != str(
                    state["pid"]
                ):
                    print(
                        "DSH tool guard did not initialize; stopping image",
                        file=sys.stderr,
                        flush=True,
                    )
                    return 1
            for child in children:
                status = child.poll()
                if status is not None:
                    print(
                        f"Required service exited with status {status}; stopping image",
                        file=sys.stderr,
                        flush=True,
                    )
                    return status if status > 0 else 1
            time.sleep(0.2)
        return 0
    except OSError as error:
        print(
            f"Unable to start a required service: {error}", file=sys.stderr, flush=True
        )
        return 1
    finally:
        stop_children(children)


if __name__ == "__main__":
    sys.exit(main())
