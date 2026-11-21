"""User-run staged Portal DB diagnosis; never print settings or exception text."""

import errno
import ipaddress
import json
import os
import socket
from contextlib import contextmanager

TIMEOUT = 5
READ_ONLY_OPTIONS = "-c default_transaction_read_only=on -c statement_timeout=5000 -c lock_timeout=5000"


def report(stage, code, **evidence):
    """Emit only fixed codes and explicitly selected noncredential evidence."""
    print(json.dumps({"stage": stage, "code": code, **evidence}), flush=True)


@contextmanager
def inspection_environment():
    """Bound libpq/SQL waits for the canonical inspector in this CLI only."""
    values = {"PGCONNECT_TIMEOUT": str(TIMEOUT), "PGOPTIONS": READ_ONLY_OPTIONS}
    previous = {key: os.environ.get(key) for key in values}
    os.environ.update(values)
    try:
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def diagnose(settings, connect, inspect):
    """Stop at the first failed layer; injected DB boundaries allow offline tests."""
    if not all((settings.psg_host, settings.psg_db, settings.psg_user, settings.psg_pass)):
        report("configuration", "missing_database_settings")
        return 2
    if not 1 <= settings.psg_port <= 65535:
        report("configuration", "invalid_database_port")
        return 2
    report("configuration", "ok")

    try:
        addresses = socket.getaddrinfo(
            settings.psg_host, settings.psg_port, type=socket.SOCK_STREAM
        )
    except OSError:
        report("dns", "resolution_failed")
        return 3
    if not addresses:
        report("dns", "no_addresses")
        return 3
    report("dns", "ok")

    reachable = False
    seen = set()
    for family, kind, protocol, _, target in addresses:
        if (family, target) in seen:
            continue
        seen.add((family, target))
        # Never echo the configured hostname, which could contain a pasted DSN.
        address = str(ipaddress.ip_address(target[0]))
        evidence = {"address": address, "port": target[1]}
        try:
            with socket.socket(family, kind, protocol) as client:
                client.settimeout(TIMEOUT)
                client.connect(target)
                evidence["source_address"] = str(
                    ipaddress.ip_address(client.getsockname()[0])
                )
        except OSError as exc:
            if isinstance(exc, TimeoutError) or exc.errno == errno.ETIMEDOUT:
                code = "timeout"
            else:
                code = {
                    errno.ECONNREFUSED: "refused",
                    errno.ENETUNREACH: "network_unreachable",
                    errno.EHOSTUNREACH: "host_unreachable",
                    errno.EACCES: "permission_denied",
                    errno.EPERM: "permission_denied",
                }.get(exc.errno, "connection_failed")
            report("tcp", code, **evidence)
        else:
            reachable = True
            report("tcp", "ok", **evidence)
    if not reachable:
        return 4

    try:
        connection = connect(
            host=settings.psg_host,
            port=settings.psg_port,
            dbname=settings.psg_db,
            user=settings.psg_user,
            password=settings.psg_pass,
            connect_timeout=TIMEOUT,
            options=READ_ONLY_OPTIONS,
        )
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                if cursor.fetchone() != (1,):
                    report("postgres", "unexpected_probe_result")
                    return 5
        finally:
            connection.close()
    except Exception as exc:
        # libpq often supplies no SQLSTATE for handshake failures. Do not guess
        # a password/HBA/TLS cause from a generic connection failure.
        code = {
            "28P01": "authentication_rejected",
            "28000": "authorization_rejected",
            "3D000": "database_missing",
            "53300": "too_many_connections",
        }.get(getattr(exc, "pgcode", None), "connection_or_query_failed")
        report("postgres", code)
        return 5
    report("postgres", "ok")

    try:
        with inspection_environment():
            status = inspect(settings)
    except Exception:
        report("schema", "inspection_failed")
        return 6
    if not status.ok:
        report("schema", "not_current_or_missing_artifacts")
        return 6
    report("schema", "ok")
    report("result", "database_checks_passed")
    return 0


def main():
    """Load the image's actual Portal settings and canonical schema inspector."""
    try:
        import psycopg2
        from settings.database import DbConnectionSettings

        from infrastructure.db.migration_check import inspect_portal_migrations
    except Exception:
        report("runtime", "dependencies_unavailable")
        return 2
    try:
        settings = DbConnectionSettings()
    except Exception:
        report("configuration", "invalid_database_settings")
        return 2
    try:
        return diagnose(settings, psycopg2.connect, inspect_portal_migrations)
    except Exception:
        # Even unexpected errors must not expose driver messages or credentials.
        report("runtime", "diagnostic_failed")
        return 7


if __name__ == "__main__":
    raise SystemExit(main())
