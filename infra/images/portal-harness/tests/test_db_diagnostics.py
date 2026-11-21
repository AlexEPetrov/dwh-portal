"""Offline diagnostic tests: all socket and database boundaries are mocked."""

import errno
import importlib.util
import io
import json
import os
import socket
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[4]
spec = importlib.util.spec_from_file_location(
    "diagnose_db", ROOT / "infra/images/portal/diagnose_db.py"
)
diagnostic = importlib.util.module_from_spec(spec)
spec.loader.exec_module(diagnostic)
IPV4 = (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("172.17.0.1", 5432))
IPV6 = (socket.AF_INET6, socket.SOCK_STREAM, 6, "", ("::1", 5432, 0, 0))


class DiagnosticTests(unittest.TestCase):
    def setUp(self):
        self.settings = SimpleNamespace(
            psg_host="configured-db",
            psg_port=5432,
            psg_db="private-db",
            psg_user="private-user",
            psg_pass="private-password",
        )
        resolver_patch = patch.object(diagnostic.socket, "getaddrinfo")
        sockets_patch = patch.object(diagnostic.socket, "socket")
        self.resolver = resolver_patch.start()
        self.sockets = sockets_patch.start()
        self.addCleanup(resolver_patch.stop)
        self.addCleanup(sockets_patch.stop)
        self.resolver.return_value = [IPV4]
        self.client = self.sockets.return_value.__enter__.return_value
        self.client.getsockname.return_value = ("172.29.0.2", 40000)
        self.connect = MagicMock()
        self.connection = self.connect.return_value
        self.cursor = self.connection.cursor.return_value.__enter__.return_value
        self.cursor.fetchone.return_value = (1,)
        self.inspect = MagicMock(return_value=SimpleNamespace(ok=True))

    def run_diagnostic(self):
        output = io.StringIO()
        with redirect_stdout(output):
            code = diagnostic.diagnose(self.settings, self.connect, self.inspect)
        text = output.getvalue()
        for secret in ("private-db", "private-user", "private-password", "raw-secret"):
            self.assertNotIn(secret, text)
        return code, [json.loads(line) for line in text.splitlines()]

    def test_success_is_staged_readonly_and_uses_canonical_inspector(self):
        def inspect(settings):
            self.assertIs(settings, self.settings)
            self.assertEqual(os.environ["PGCONNECT_TIMEOUT"], "5")
            self.assertEqual(os.environ["PGOPTIONS"], diagnostic.READ_ONLY_OPTIONS)
            return SimpleNamespace(ok=True)

        self.inspect.side_effect = inspect
        with patch.dict(
            os.environ, {"PGOPTIONS": "original", "PGCONNECT_TIMEOUT": "19"}
        ):
            code, rows = self.run_diagnostic()
            self.assertEqual(os.environ["PGOPTIONS"], "original")
            self.assertEqual(os.environ["PGCONNECT_TIMEOUT"], "19")
        self.assertEqual(code, 0)
        self.assertEqual(
            [row["stage"] for row in rows],
            ["configuration", "dns", "tcp", "postgres", "schema", "result"],
        )
        self.assertEqual(rows[2]["source_address"], "172.29.0.2")
        self.client.settimeout.assert_called_once_with(5)
        self.connect.assert_called_once_with(
            host="configured-db",
            port=5432,
            dbname="private-db",
            user="private-user",
            password="private-password",
            connect_timeout=5,
            options=diagnostic.READ_ONLY_OPTIONS,
        )
        self.cursor.execute.assert_called_once_with("SELECT 1")
        self.connection.close.assert_called_once_with()
        self.inspect.assert_called_once_with(self.settings)

    def test_missing_settings_and_bad_port_stop_before_dns(self):
        for key, value, expected in (
            ("psg_host", "", "missing_database_settings"),
            ("psg_pass", "", "missing_database_settings"),
            ("psg_port", 0, "invalid_database_port"),
            ("psg_port", 65536, "invalid_database_port"),
        ):
            with self.subTest(key=key, value=value):
                old = getattr(self.settings, key)
                setattr(self.settings, key, value)
                code, rows = self.run_diagnostic()
                setattr(self.settings, key, old)
                self.assertEqual(code, 2)
                self.assertEqual(rows[-1]["code"], expected)
        self.resolver.assert_not_called()
        self.connect.assert_not_called()

    def test_resolution_failure_and_empty_results_stop_before_tcp(self):
        for error, expected in (
            (socket.gaierror("raw-secret"), "resolution_failed"),
            (None, "no_addresses"),
        ):
            self.resolver.side_effect = error
            self.resolver.return_value = []
            code, rows = self.run_diagnostic()
            self.assertEqual(code, 3)
            self.assertEqual(rows[-1]["code"], expected)
        self.sockets.assert_not_called()
        self.connect.assert_not_called()

    def test_tcp_failures_are_not_reported_as_authentication(self):
        for error, expected in (
            (TimeoutError("raw-secret"), "timeout"),
            (OSError(errno.ETIMEDOUT, "raw-secret"), "timeout"),
            (OSError(errno.ECONNREFUSED, "raw-secret"), "refused"),
            (OSError(errno.ENETUNREACH, "raw-secret"), "network_unreachable"),
            (OSError(errno.EHOSTUNREACH, "raw-secret"), "host_unreachable"),
            (OSError(errno.EACCES, "raw-secret"), "permission_denied"),
            (OSError(errno.EIO, "raw-secret"), "connection_failed"),
        ):
            with self.subTest(expected=expected):
                self.client.connect.side_effect = error
                code, rows = self.run_diagnostic()
                self.assertEqual(code, 4)
                self.assertEqual(rows[-1]["stage"], "tcp")
                self.assertEqual(rows[-1]["code"], expected)
        self.connect.assert_not_called()
        self.inspect.assert_not_called()

    def test_unique_addresses_are_probed_and_partial_success_continues(self):
        self.resolver.return_value = [IPV6, IPV6, IPV4]
        self.client.connect.side_effect = [TimeoutError(), None]
        code, rows = self.run_diagnostic()
        self.assertEqual(code, 0)
        self.assertEqual(
            [row["code"] for row in rows if row["stage"] == "tcp"], ["timeout", "ok"]
        )
        self.assertEqual(self.sockets.call_count, 2)

    def test_handshake_errors_use_known_sqlstates_not_exception_messages(self):
        for state, expected in (
            (None, "connection_or_query_failed"),
            ("28P01", "authentication_rejected"),
            ("28000", "authorization_rejected"),
            ("3D000", "database_missing"),
            ("53300", "too_many_connections"),
        ):
            error = RuntimeError("raw-secret")
            error.pgcode = state
            self.connect.side_effect = error
            code, rows = self.run_diagnostic()
            self.assertEqual(code, 5)
            self.assertEqual(rows[-1]["code"], expected)
        self.inspect.assert_not_called()

    def test_probe_failure_closes_connection_and_skips_schema(self):
        self.cursor.execute.side_effect = RuntimeError("raw-secret")
        code, rows = self.run_diagnostic()
        self.assertEqual(code, 5)
        self.assertEqual(rows[-1]["stage"], "postgres")
        self.connection.close.assert_called_once_with()
        self.inspect.assert_not_called()

    def test_schema_errors_are_distinct_from_tcp_and_restore_environment(self):
        for status, error, expected in (
            (SimpleNamespace(ok=False), None, "not_current_or_missing_artifacts"),
            (None, RuntimeError("raw-secret"), "inspection_failed"),
        ):
            self.inspect.return_value = status
            self.inspect.side_effect = error
            with patch.dict(os.environ, {"PGOPTIONS": "original"}):
                code, rows = self.run_diagnostic()
                self.assertEqual(os.environ["PGOPTIONS"], "original")
            self.assertEqual(code, 6)
            self.assertEqual(rows[-1], {"stage": "schema", "code": expected})

    def test_image_includes_diagnostic_and_preserves_startup(self):
        base = ROOT / "infra/images/portal"
        dockerfile = (base / "Dockerfile").read_text()
        self.assertIn(
            "COPY infra/images/portal/diagnose_db.py /opt/portal/diagnose_db.py",
            dockerfile,
        )
        self.assertIn('CMD ["python3", "src/api/run.py"]', dockerfile)
        self.assertIn(
            "!infra/images/portal/diagnose_db.py",
            (base / "Dockerfile.dockerignore").read_text(),
        )
        compile((base / "diagnose_db.py").read_text(), "diagnose_db.py", "exec")


if __name__ == "__main__":
    unittest.main()
