"""Offline startup check of Portal, DSH token exchange and bundled Web UI."""

import json
import os
import re
import subprocess
import sys
import tempfile
import time
from http.cookies import SimpleCookie
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def redact(text):
    return re.sub(r"([?&](?:token|key|auth)=)[^&\s\"'<>]+", r"\1[redacted]", text)


def launch_url(text):
    clean = re.sub(r"\x1b\[[0-9;]*m", "", text)
    match = re.search(r"dsh web:\s*(https?://[^\s]+)", clean)
    if not match:
        return None
    url = urlsplit(match.group(1))
    if url.netloc != "127.0.0.1:3080" or url.scheme != "http" or not url.query:
        raise RuntimeError("Unexpected DSH entry URL; refusing to follow it")
    return url


def main():
    release = json.loads(Path(__file__).with_name("dsh-source.json").read_text())
    environment = dict(os.environ)
    environment.update(
        {
            "APP_PORTAL_STORE": "memory",
            "APP_PORTAL_SEED_DEMO": "true",
            "APP_API_PORT": "5051",
            "APP_MCP_ENABLED": "true",
            "APP_MCP_ALLOW_ANONYMOUS_READ": "true",
            "DSH_PORT": "3080",
            "DSH_PROVIDER_MODE": "ollama",
            "DSH_OLLAMA_BASE_URL": "",
            "DSH_OLLAMA_MODEL": "",
            "DSH_BIND_HOST": "127.0.0.1",
            "DSH_PUBLIC_URL": "http://127.0.0.1:3080/",
        }
    )
    opener = build_opener(ProxyHandler({}), NoRedirect())
    with tempfile.TemporaryDirectory() as temporary:
        log_path = Path(temporary) / "startup.log"
        with log_path.open("w") as log:
            child = subprocess.Popen(
                [sys.executable, "/opt/portal-harness/launch.py", "all"],
                env=environment,
                stdout=log,
                stderr=log,
            )
        try:
            deadline = time.monotonic() + 120
            while True:
                if child.poll() is not None:
                    raise RuntimeError(f"Launcher exited early: {child.returncode}")
                entry = launch_url(log_path.read_text())
                try:
                    if entry is None:
                        raise URLError("Waiting for DSH entry")
                    with opener.open(
                        "http://127.0.0.1:5051/health", timeout=2
                    ) as response:
                        if response.status != 200:
                            raise RuntimeError("Portal health failed")
                    subprocess.run(
                        [sys.executable, "/opt/portal-harness/healthcheck.py"],
                        env=environment,
                        check=True,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                    break
                except (URLError, TimeoutError, subprocess.CalledProcessError):
                    if time.monotonic() >= deadline:
                        raise RuntimeError(
                            "Timed out waiting for both guarded services"
                        ) from None
                    time.sleep(0.5)
            try:
                opener.open("http://127.0.0.1:3080/", timeout=3).close()
            except HTTPError as error:
                if error.code != 401:
                    raise RuntimeError(
                        "DSH did not reject anonymous index access"
                    ) from None
            else:
                raise RuntimeError("DSH index is not protected")
            try:
                opener.open(f"http://127.0.0.1:3080/?{entry.query}", timeout=5).close()
            except HTTPError as error:
                if error.code != 303:
                    raise RuntimeError("DSH token exchange did not redirect") from None
                cookies = SimpleCookie()
                for value in error.headers.get_all("Set-Cookie", []):
                    cookies.load(value)
                if not cookies:
                    raise RuntimeError("DSH token exchange issued no cookie")
            else:
                raise RuntimeError("DSH token exchange did not issue a redirect")
            cookie = "; ".join(f"{key}={value.value}" for key, value in cookies.items())
            for url in ("http://127.0.0.1:5051/", "http://127.0.0.1:3080/"):
                headers = {"Cookie": cookie} if ":3080/" in url else {}
                with opener.open(Request(url, headers=headers), timeout=5) as response:
                    if (
                        response.status != 200
                        or "text/html" not in response.headers.get("Content-Type", "")
                    ):
                        raise RuntimeError("Bundled HTML was not served")
            version = subprocess.check_output(
                ["/usr/local/bin/dsh", "--version"], text=True
            ).strip()
            if version != release["version"]:
                raise RuntimeError("DSH version does not match the source pin")
            subprocess.run(
                ["/usr/local/bin/node", "/opt/portal-harness/check_catalog_mcp.mjs"],
                env=environment,
                check=True,
                timeout=45,
            )
            child.terminate()
            if child.wait(timeout=20) != 0:
                raise RuntimeError("Launcher did not shut down cleanly")
            print(
                f"PASS: Portal UI/health/MCP, source-built DSH {version}, token/cookie auth, "
                "tool guard, actual host catalog registration, shutdown (no model roundtrip)"
            )
        except BaseException:
            print(redact(log_path.read_text()), file=sys.stderr)
            raise
        finally:
            if child.poll() is None:
                child.terminate()
                try:
                    child.wait(timeout=20)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait()


if __name__ == "__main__":
    main()
