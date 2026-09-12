from __future__ import annotations

import datetime
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from domains.catalog.identity import (
    airflow_extraction_identity,
    airflow_process_identity,
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
_DAG_START = re.compile(r"(?<![A-Za-z0-9_])(?:DAG|@dag)\s*\(", re.IGNORECASE)
_DAG_ID_KW = re.compile(
    r"""\bdag_id\s*=\s*(?:'''(.*?)'''|\"\"\"(.*?)\"\"\"|['\"]([^'\"]+)['\"])""",
    re.DOTALL,
)
_DESCRIPTION_KW = re.compile(
    r"""\bdescription\s*=\s*(?:'''(.*?)'''|\"\"\"(.*?)\"\"\"|['\"]([^'\"]*)['\"])""",
    re.DOTALL,
)
_POS_STRING = re.compile(
    r"""^\s*(?:'''(.*?)'''|\"\"\"(.*?)\"\"\"|['\"]([^'\"]+)['\"])""",
    re.DOTALL,
)


@dataclass(frozen=True)
class DagMeta:
    dag_id: str | None = None
    description: str | None = None


class AirflowDagsLineageAdapter:
    """Reverse-reconstruct EXTRACTION_SOURCE -> PROCESS -> TABLE from DAG text."""

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
        details = {
            "files": 0,
            "processes": 0,
            "extraction_sources": 0,
            "writes": 0,
        }
        try:
            tables = self._catalog_write_targets()
            files = list(self._iter_python_files(path))
            details["files"] = len(files)
            by_dir: dict[Path, list[tuple[Path, str]]] = {}
            for file_path, text in files:
                by_dir.setdefault(file_path.parent, []).append((file_path, text))
            seen_processes: set[str] = set()
            for file_path, text in files:
                created = self._ingest_file(
                    path, file_path, text, tables, by_dir.get(file_path.parent, []), started, details
                )
                if created and created not in seen_processes:
                    seen_processes.add(created)
                    details["processes"] += 1
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
        root: Path,
        file_path: Path,
        text: str,
        tables: list[Asset],
        dir_files: list[tuple[Path, str]],
        now: datetime.datetime,
        details: dict,
    ) -> str | None:
        matched = [asset for asset in tables if self._mentions(text, asset, tables)]
        if not matched:
            return None
        dag_path, dag_text = _resolve_dag_module(file_path, text, dir_files)
        process_path = dag_path or file_path
        meta = parse_dag_meta(dag_text if dag_path else text)
        module_name = _module_name(process_path, root)
        process = self._upsert_process(module_name, process_path, meta, now)
        extraction = self._upsert_extraction(module_name, meta, process_path, now)
        details["extraction_sources"] += 1
        self._rel(extraction.id, process.id, RelationshipType.EXTRACTS_TO)
        for table in matched:
            self._rel(process.id, table.id, RelationshipType.WRITES_TO)
            details["writes"] += 1
        return module_name

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

    def _upsert_process(
        self, module_name: str, file_path: Path, meta: DagMeta, now: datetime.datetime
    ) -> Asset:
        qualified_name, identity_key = airflow_process_identity(module_name)
        existing = self._store.find_by_identity(PROVIDER, identity_key)
        attributes = {
            "handler_type": "AirflowDag",
            "module_name": module_name,
            "dag_id": meta.dag_id,
            "source_path": str(file_path),
            "metadata_status": "OK",
            "lineage_status": "RESOLVED",
        }
        display_name = Path(module_name).name
        description = meta.description or f"Airflow DAG module {display_name}"
        if existing is not None:
            existing.last_seen_at = now
            existing.deleted_at = None
            existing.name = display_name
            existing.description = description
            existing.attributes = {**existing.attributes, **attributes}
            return self._store.upsert_asset(existing)
        return self._store.upsert_asset(
            Asset(
                asset_type=AssetType.PROCESS,
                qualified_name=qualified_name,
                name=display_name,
                description=description,
                source_provider=PROVIDER,
                identity_key=identity_key,
                first_seen_at=now,
                last_seen_at=now,
                attributes=attributes,
            )
        )

    def _upsert_extraction(
        self, module_name: str, meta: DagMeta, file_path: Path, now: datetime.datetime
    ) -> Asset:
        native_id = meta.dag_id or module_name
        qualified_name, identity_key = airflow_extraction_identity(native_id)
        existing = self._store.find_by_identity(PROVIDER, identity_key)
        attributes = {
            "dag_id": meta.dag_id,
            "module_name": module_name,
            "source_path": str(file_path),
            "origin": "airflow_dag",
        }
        name = meta.dag_id or Path(module_name).name
        description = meta.description
        if existing is not None:
            existing.last_seen_at = now
            existing.deleted_at = None
            existing.name = name
            if description:
                existing.description = description
            existing.attributes = {**existing.attributes, **attributes}
            return self._store.upsert_asset(existing)
        return self._store.upsert_asset(
            Asset(
                asset_type=AssetType.EXTRACTION_SOURCE,
                qualified_name=qualified_name,
                name=name,
                description=description,
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


def _module_name(file_path: Path, root: Path) -> str:
    try:
        relative = file_path.resolve().relative_to(root.resolve())
    except ValueError:
        return file_path.stem
    return relative.with_suffix("").as_posix()


def is_dag_module(text: str) -> bool:
    return _DAG_START.search(text) is not None


def _resolve_dag_module(
    file_path: Path, text: str, dir_files: list[tuple[Path, str]]
) -> tuple[Path | None, str]:
    if is_dag_module(text):
        return file_path, text
    for other_path, other_text in sorted(dir_files, key=lambda item: str(item[0])):
        if other_path == file_path:
            continue
        if is_dag_module(other_text):
            return other_path, other_text
    return None, text


def parse_dag_meta(text: str) -> DagMeta:
    """Read dag_id and description from the first DAG(...) / @dag(...) call."""
    match = _DAG_START.search(text)
    if match is None:
        return DagMeta()
    open_idx = match.end() - 1
    body = _paren_body(text, open_idx)
    if not body:
        return DagMeta()
    dag_id = _first_string(_DAG_ID_KW.search(body)) or _first_string(_POS_STRING.search(body))
    description = _first_string(_DESCRIPTION_KW.search(body))
    if description:
        description = " ".join(description.split())
    return DagMeta(dag_id=dag_id, description=description or None)


def _paren_body(text: str, open_idx: int) -> str | None:
    if open_idx >= len(text) or text[open_idx] != "(":
        return None
    depth = 0
    i = open_idx
    quote: str | None = None
    triple = False
    escape = False
    while i < len(text):
        ch = text[i]
        if quote is not None:
            if escape:
                escape = False
            elif ch == "\\" and not triple:
                escape = True
            elif triple and text.startswith(quote, i):
                i += 2
                quote = None
                triple = False
            elif not triple and ch == quote:
                quote = None
            i += 1
            continue
        if text.startswith("'''", i) or text.startswith('"""', i):
            quote = text[i : i + 3]
            triple = True
            i += 3
            continue
        if ch in {"'", '"'}:
            quote = ch
            triple = False
            i += 1
            continue
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return text[open_idx + 1 : i]
        i += 1
    return None


def _first_string(match: re.Match[str] | None) -> str | None:
    if match is None:
        return None
    for group in match.groups():
        if group is not None and group != "":
            return group
    return None


def _has_token(text: str, needle: str) -> bool:
    pattern = r"(?<![A-Za-z0-9_])" + re.escape(needle) + r"(?![A-Za-z0-9_])"
    return re.search(pattern, text) is not None


def _has_quoted(text: str, name: str) -> bool:
    return re.search(r"['\"]" + re.escape(name) + r"['\"]", text) is not None
