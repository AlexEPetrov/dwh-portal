from __future__ import annotations

import datetime
import re
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlsplit, urlunsplit

from domains.catalog.identity import (
    airflow_process_identity,
    url_data_source_identity,
)
from domains.catalog.lineage_adapters.runs import record_adapter_run, skipped_run
from domains.catalog.models import (
    Asset,
    AssetQuery,
    AssetStatus,
    AssetType,
    CollectionRun,
    CollectorStatus,
    Relationship,
    RelationshipType,
)
from domains.catalog.repositories.ports import PortalStore
from settings.portal import DwhCollectorSettings

PROVIDER = "airflow_dags"
WRITE_TYPES = {AssetType.TABLE, AssetType.MATERIALIZED_VIEW}
MAX_FILE_BYTES = 1_000_000
SKIP_DIRS = {".git", ".venv", "venv", "__pycache__", "node_modules", ".mypy_cache"}
UNQUALIFIED_STOPLIST = frozenset(
    {
        "data",
        "table",
        "name",
        "value",
        "type",
        "date",
        "test",
        "main",
        "config",
        "source",
        "target",
        "user",
        "file",
        "path",
        "sql",
        "dag",
        "task",
    }
)
SKIP_URL_HOSTS = frozenset(
    {
        "localhost",
        "127.0.0.1",
        "airflow.apache.org",
        "www.airflow.apache.org",
        "pypi.org",
        "www.pypi.org",
    }
)
_DAG_ID_KW = re.compile(r"""\bdag_id\s*=\s*['"]([^'"]+)['"]""")
_DAG_POS = re.compile(r"""\bDAG\s*\(\s*['"]([^'"]+)['"]""")
_URL_RE = re.compile(r"""(?i)\b(?:https?|s3|gs|ftp|sftp)://[^\s'\"\\)<>]+""")


class AirflowDagsLineageAdapter:
    """Reverse-reconstruct PROCESS/DATA_SOURCE edges from DAG source text."""

    name = "airflow_dags"

    def __init__(
        self,
        store: PortalStore,
        settings: DwhCollectorSettings | None = None,
        **_kwargs: Any,
    ):
        self._store = store
        self._settings = settings or DwhCollectorSettings()

    def collect(self, now: datetime.datetime | None = None) -> CollectionRun:
        started = now or datetime.datetime.now(datetime.timezone.utc)
        root = (self._settings.airflow_dags_root or "").strip()
        if not root:
            return skipped_run(
                self._store,
                name=self.name,
                started=started,
                reason="DAGS_ROOT_MISSING",
                message="Airflow DAG root is not configured",
            )
        path = Path(root)
        if not path.is_dir():
            return skipped_run(
                self._store,
                name=self.name,
                started=started,
                reason="DAGS_ROOT_MISSING",
                message=f"Airflow DAG root does not exist: {root}",
            )
        details = {"files": 0, "processes": 0, "data_sources": 0, "writes": 0}
        try:
            tables = self._catalog_write_targets()
            for file_path, text in self._iter_python_files(path):
                details["files"] += 1
                self._ingest_file(file_path, text, tables, started, details)
            message = (
                f"Scanned {details['files']} DAG files, "
                f"{details['processes']} processes, {details['writes']} writes"
            )
            status = CollectorStatus.SUCCESS
        except Exception as exc:
            return record_adapter_run(
                self._store,
                name=self.name,
                started=started,
                status=CollectorStatus.FAILED,
                message=str(exc),
                details={"error": str(exc)},
            )
        return record_adapter_run(
            self._store,
            name=self.name,
            started=started,
            status=status,
            message=message,
            details=details,
        )

    def _catalog_write_targets(self) -> list[Asset]:
        assets, _ = self._store.list_assets(
            AssetQuery(status=AssetStatus.ACTIVE, page=1, page_size=10_000)
        )
        return [item for item in assets if item.asset_type in WRITE_TYPES]

    def _ingest_file(
        self,
        file_path: Path,
        text: str,
        tables: list[Asset],
        now: datetime.datetime,
        details: dict,
    ) -> None:
        matched = [asset for asset in tables if self._mentions(text, asset, tables)]
        if not matched:
            return
        dag_id = self._dag_id(text, file_path)
        process = self._upsert_process(dag_id, file_path, now)
        details["processes"] += 1
        for table in matched:
            self._rel(process.id, table.id, RelationshipType.WRITES_TO)
            details["writes"] += 1
        for url in self._extract_urls(text):
            source = self._upsert_url_source(url, now)
            self._rel(process.id, source.id, RelationshipType.READS_FROM)
            details["data_sources"] += 1

    def _mentions(self, text: str, asset: Asset, all_tables: list[Asset]) -> bool:
        schema = str(asset.attributes.get("schema") or "")
        database = str(asset.attributes.get("database") or "")
        name = asset.name
        if schema and _has_token(text, f"{schema}.{name}"):
            return True
        if database and schema and _has_token(text, f"{database}.{schema}.{name}"):
            return True
        if len(name) < 4 or name.lower() in UNQUALIFIED_STOPLIST:
            return False
        if sum(1 for item in all_tables if item.name == name) != 1:
            return False
        return _has_quoted(text, name) or _has_token(text, name)

    def _dag_id(self, text: str, file_path: Path) -> str:
        keyword = _DAG_ID_KW.search(text)
        if keyword:
            return keyword.group(1)
        positional = _DAG_POS.search(text)
        if positional:
            return positional.group(1)
        return file_path.stem

    def _upsert_process(self, dag_id: str, file_path: Path, now: datetime.datetime) -> Asset:
        qualified_name, identity_key = airflow_process_identity(dag_id)
        existing = self._store.find_by_identity(PROVIDER, identity_key)
        attributes = {
            "handler_type": "AirflowDag",
            "dag_id": dag_id,
            "source_path": str(file_path),
            "metadata_status": "OK",
            "lineage_status": "RESOLVED",
        }
        if existing is not None:
            existing.last_seen_at = now
            existing.deleted_at = None
            existing.name = dag_id
            existing.attributes = {**existing.attributes, **attributes}
            return self._store.upsert_asset(existing)
        return self._store.upsert_asset(
            Asset(
                asset_type=AssetType.PROCESS,
                qualified_name=qualified_name,
                name=dag_id,
                description=f"Airflow DAG {dag_id}",
                source_provider=PROVIDER,
                identity_key=identity_key,
                first_seen_at=now,
                last_seen_at=now,
                attributes=attributes,
            )
        )

    def _upsert_url_source(self, url: str, now: datetime.datetime) -> Asset:
        qualified_name, identity_key = url_data_source_identity(url)
        existing = self._store.find_by_identity(PROVIDER, identity_key)
        attributes = {"url": url, "origin": "airflow_dag"}
        if existing is not None:
            existing.last_seen_at = now
            existing.deleted_at = None
            existing.attributes = {**existing.attributes, **attributes}
            return self._store.upsert_asset(existing)
        return self._store.upsert_asset(
            Asset(
                asset_type=AssetType.DATA_SOURCE,
                qualified_name=qualified_name,
                name=url,
                description=url,
                source_provider=PROVIDER,
                identity_key=identity_key,
                first_seen_at=now,
                last_seen_at=now,
                attributes=attributes,
            )
        )

    def _rel(self, from_id, to_id, rel_type: RelationshipType) -> None:
        self._store.upsert_relationship(
            Relationship(
                from_asset_id=from_id,
                to_asset_id=to_id,
                relationship_type=rel_type,
                source_provider=PROVIDER,
            )
        )

    def _iter_python_files(self, root: Path) -> Iterable[tuple[Path, str]]:
        for path in sorted(root.rglob("*.py")):
            if any(part in SKIP_DIRS for part in path.parts):
                continue
            if path.name.startswith("test_") or path.name.endswith("_test.py"):
                continue
            if path.name == "conftest.py":
                continue
            try:
                size = path.stat().st_size
            except OSError:
                continue
            if size > MAX_FILE_BYTES:
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            yield path, text

    def _extract_urls(self, text: str) -> list[str]:
        found: list[str] = []
        seen: set[str] = set()
        for match in _URL_RE.findall(text):
            normalized = normalize_url(match)
            if normalized is None or normalized in seen:
                continue
            seen.add(normalized)
            found.append(normalized)
        return found


def _has_token(text: str, needle: str) -> bool:
    pattern = r"(?<![A-Za-z0-9_])" + re.escape(needle) + r"(?![A-Za-z0-9_])"
    return re.search(pattern, text) is not None


def _has_quoted(text: str, name: str) -> bool:
    return re.search(r"['\"]" + re.escape(name) + r"['\"]", text) is not None


def normalize_url(raw: str) -> str | None:
    """Drop credentials and query; skip documentation/local hosts."""
    cleaned = raw.rstrip(".,;)]}'\"")
    parts = urlsplit(cleaned)
    host = (parts.hostname or "").lower()
    if not parts.scheme or not host or host in SKIP_URL_HOSTS:
        return None
    netloc = host
    if parts.port:
        netloc = f"{host}:{parts.port}"
    path = parts.path.rstrip("/")
    return urlunsplit((parts.scheme.lower(), netloc, path, "", ""))
