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
from urllib.parse import urlsplit

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


def provider_environment(environment: dict[str, str]) -> dict[str, str]:
    """Select an explicit provider profile without contacting any model endpoint."""
    mode = environment.get("DSH_PROVIDER_MODE", "ollama")
    if mode not in {"ollama", "upstream"}:
        raise ValueError("DSH_PROVIDER_MODE must be ollama or upstream")
    result = {"PORTAL_PROVIDER_MODE": mode}
    if mode == "upstream":
        return result

    base_url = environment.get("DSH_OLLAMA_BASE_URL", "").strip()
    model = environment.get("DSH_OLLAMA_MODEL", "").strip()
    if bool(base_url) != bool(model):
        raise ValueError(
            "Set both DSH_OLLAMA_BASE_URL and DSH_OLLAMA_MODEL, or neither"
        )
    profiles = {}
    if base_url:
        parsed = urlsplit(base_url)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
            or not parsed.path.rstrip("/").endswith("/v1")
        ):
            raise ValueError(
                "DSH_OLLAMA_BASE_URL must be an HTTP(S) /v1 URL without credentials or query"
            )
        try:
            context = int(environment.get("DSH_OLLAMA_CONTEXT_WINDOW", "8192"))
            output = int(environment.get("DSH_OLLAMA_MAX_TOKENS", "2048"))
        except ValueError:
            raise ValueError(
                "Ollama context/output limits must be positive integers"
            ) from None
        if not 0 < output < context:
            raise ValueError(
                "Ollama output limit must be positive and smaller than its context window"
            )
        profiles["portal-ollama"] = {
            "displayName": "Internal Ollama",
            "api": "openai-completions",
            "baseURL": base_url.rstrip("/"),
            "apiKeyEnv": "PORTAL_OLLAMA_API_KEY",
            "models": [{"id": model, "contextWindow": context, "maxTokens": output}],
        }
        result["PORTAL_OLLAMA_MODEL"] = model
        # Ollama ignores this public placeholder. A secured internal gateway can
        # supply its own key; configuration contains only the credential reference.
        result["PORTAL_OLLAMA_API_KEY"] = (
            environment.get("DSH_OLLAMA_API_KEY") or "ollama"
        )
    result["PORTAL_OLLAMA_PROVIDERS"] = json.dumps(profiles)
    return result


def harness_environment(environment: dict[str, str]) -> dict[str, str]:
    """Avoid passing Portal/database secrets to the harness child process."""
    providers = provider_environment(environment)
    result = {
        key: value
        for key, value in environment.items()
        if key in SHARED_ENV
        or (
            providers["PORTAL_PROVIDER_MODE"] == "upstream"
            and key.startswith(PROVIDER_PREFIXES)
        )
    }
    result.update(providers)
    result.update(
        {
            "HOME": "/var/lib/dsh",
            "DSH_HOME": "/var/lib/dsh",
            "DSH_AGENTS_HOME": "/var/lib/dsh/agents",
            "DSH_TELEMETRY_DISABLED": "1",
            "PORTAL_MCP_URL": f"http://127.0.0.1:{port(environment.get('APP_API_PORT', '5051'))}/mcp",
        }
    )
    # This is a credential reference, never the token itself. The owner stores
    # its value in DSH's credentials provider; raw config keeps only a template.
    if environment.get("DSH_PORTAL_MCP_CREDENTIAL"):
        result["PORTAL_MCP_CREDENTIAL"] = environment["DSH_PORTAL_MCP_CREDENTIAL"]
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
        # Opt-in experimental image only; ordinary Portal settings stay disabled.
        # The owner explicitly approved this temporary anonymous read exception.
        portal_env.setdefault("APP_MCP_ENABLED", "true")
        portal_env.setdefault("APP_MCP_ALLOW_ANONYMOUS_READ", "true")
        portal_env.setdefault("APP_MCP_PUBLIC_BASE_URL", "http://127.0.0.1:5053")
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
