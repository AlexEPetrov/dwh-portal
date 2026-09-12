from __future__ import annotations

import datetime
import re
from pathlib import Path
from typing import Any, Iterable

from domains.catalog.identity import (
    airflow_extraction_identity,
    airflow_process_identity,
    storage_location_identity,
    unresolved_target_identity,
)
from domains.catalog.lineage_adapters.airflow_syntax import (
    DagMeta,
    TableRef,
    bind_imported_constants,
    dag_closure,
    parse_module,
    rescan_writes,
    storage_paths_for_closure,
    write_targets_for_closure,
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


class AirflowDagsLineageAdapter:
    """Reverse-reconstruct EXTRACTION_SOURCE -> PROCESS -> TABLE from DAG AST."""

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
        mode = _lineage_mode(self._settings)
        details = {
            "files": 0,
            "dags": 0,
            "processes": 0,
            "extraction_sources": 0,
            "writes": 0,
            "storages": 0,
            "unresolved": 0,
            "mode": mode,
        }
        try:
            catalog_tables = self._catalog_write_targets()
            files = list(self._iter_python_files(path))
            details["files"] = len(files)
            facts_by_path = {}
            for file_path, text in files:
                facts = parse_module(file_path.resolve(), text)
                if facts is not None:
                    facts_by_path[file_path.resolve()] = facts
            resolved_root = path.resolve()
            bind_imported_constants(facts_by_path, resolved_root)
            for facts in facts_by_path.values():
                rescan_writes(facts)
            seen_processes: set[str] = set()
            for dag_path, facts in facts_by_path.items():
                if not facts.is_dag:
                    continue
                details["dags"] += 1
                closure = dag_closure(dag_path, facts_by_path, resolved_root)
                has_write = any(
                    facts_by_path[item].has_write
                    for item in closure
                    if item in facts_by_path
                )
                refs = write_targets_for_closure(closure, facts_by_path) if has_write else []
                matched = self._match_tables(refs, catalog_tables, started, mode, resolved_root)
                path_refs = (
                    storage_paths_for_closure(closure, facts_by_path) if mode == "code" else []
                )
                if not matched and not path_refs:
                    continue
                meta = facts.dag_meta
                if not meta.dag_id and not meta.description:
                    meta = parse_dag_meta(facts.source)
                module_name = _module_name(dag_path, resolved_root)
                dag_files = _relative_sources([str(dag_path)], resolved_root)
                process = self._upsert_process(module_name, dag_path, meta, started, dag_files)
                extraction = self._upsert_extraction(
                    module_name, meta, dag_path, started, dag_files
                )
                details["extraction_sources"] += 1
                self._rel(extraction.id, process.id, RelationshipType.EXTRACTS_TO)
                for table in matched:
                    self._rel(process.id, table.id, RelationshipType.WRITES_TO)
                    details["writes"] += 1
                    if table.attributes.get("unresolved"):
                        details["unresolved"] += 1
                for path_ref in path_refs:
                    storage = self._upsert_storage(
                        path_ref.path,
                        _relative_sources([path_ref.source_path], resolved_root),
                        started,
                    )
                    self._rel(process.id, storage.id, RelationshipType.READS_FROM)
                    details["storages"] += 1
                if module_name not in seen_processes:
                    seen_processes.add(module_name)
                    details["processes"] += 1
            message = (
                f"Scanned {details['files']} files, {details['dags']} DAGs, "
                f"{details['processes']} processes, {details['writes']} writes, "
                f"{details['storages']} storages"
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

    def _match_tables(
        self,
        refs: list[TableRef],
        tables: list[Asset],
        now: datetime.datetime,
        mode: str,
        root: Path,
    ) -> list[Asset]:
        matched: list[Asset] = []
        seen: set[str] = set()
        for ref in refs:
            asset = self._match_table(ref, tables, now, mode)
            if asset is None:
                continue
            files = _relative_sources([ref.source_path], root)
            asset = self._attach_source_files(asset, files)
            if str(asset.id) in seen:
                continue
            seen.add(str(asset.id))
            matched.append(asset)
        return matched

    def _match_table(
        self,
        ref: TableRef,
        tables: list[Asset],
        now: datetime.datetime,
        mode: str,
    ) -> Asset | None:
        name = ref.name
        schema = ref.schema
        if "." in name and schema is None:
            parts = name.split(".")
            if len(parts) == 2:
                schema, name = parts
            elif len(parts) == 3:
                schema, name = parts[1], parts[2]
        if not name or name.lower() in UNQUALIFIED_STOPLIST:
            return None
        if schema:
            hits = [
                item
                for item in tables
                if item.name.lower() == name.lower()
                and str(item.attributes.get("schema") or "").lower() == schema.lower()
                and not item.attributes.get("unresolved")
            ]
            if len(hits) == 1:
                return hits[0]
        if len(name) >= 4:
            hits = [
                item
                for item in tables
                if item.name.lower() == name.lower() and not item.attributes.get("unresolved")
            ]
            if len(hits) == 1:
                return hits[0]
        if mode == "code":
            return self._unresolved_table(schema or "_", name, now)
        return None

    def _unresolved_table(self, schema: str, name: str, now: datetime.datetime) -> Asset:
        database = self._settings.connection_identity or "dwh"
        qualified_name, identity_key = unresolved_target_identity(database, schema, name)
        existing = self._store.find_by_identity(PROVIDER, identity_key)
        attributes = {
            "unresolved": True,
            "target_ref": {"database": database, "schema": schema, "name": name},
            "database": database,
            "schema": schema,
            "display_name": f"{schema}.{name}",
        }
        if existing is not None:
            existing.last_seen_at = now
            existing.deleted_at = None
            existing.attributes = {**existing.attributes, **attributes}
            return self._store.upsert_asset(existing)
        return self._store.upsert_asset(
            Asset(
                asset_type=AssetType.TABLE,
                qualified_name=qualified_name,
                name=name,
                source_provider=PROVIDER,
                identity_key=identity_key,
                first_seen_at=now,
                last_seen_at=now,
                attributes=attributes,
            )
        )

    def _upsert_storage(self, path: str, source_files: list[str], now: datetime.datetime) -> Asset:
        qualified_name, identity_key = storage_location_identity(path)
        existing = self._store.find_by_identity(PROVIDER, identity_key)
        if existing is None:
            existing = self._store.find_by_qualified_name(qualified_name)
        attributes = {
            "path": path,
            "origin": "airflow_dag",
            "source_files": source_files,
            "display_name": path,
        }
        if existing is not None:
            existing.last_seen_at = now
            existing.deleted_at = None
            merged = {**existing.attributes, **attributes}
            merged["source_files"] = _merge_source_files(
                existing.attributes.get("source_files"), source_files
            )
            existing.attributes = merged
            return self._store.upsert_asset(existing)
        return self._store.upsert_asset(
            Asset(
                asset_type=AssetType.STORAGE_LOCATION,
                qualified_name=qualified_name,
                name=path,
                source_provider=PROVIDER,
                identity_key=identity_key,
                first_seen_at=now,
                last_seen_at=now,
                attributes=attributes,
            )
        )

    def _attach_source_files(self, asset: Asset, files: list[str]) -> Asset:
        if not files:
            return asset
        asset.attributes = {
            **asset.attributes,
            "source_files": _merge_source_files(asset.attributes.get("source_files"), files),
        }
        return self._store.upsert_asset(asset)

    def _upsert_process(
        self,
        module_name: str,
        file_path: Path,
        meta: DagMeta,
        now: datetime.datetime,
        source_files: list[str],
    ) -> Asset:
        qualified_name, identity_key = airflow_process_identity(module_name)
        existing = self._store.find_by_identity(PROVIDER, identity_key)
        attributes = {
            "handler_type": "AirflowDag",
            "module_name": module_name,
            "dag_id": meta.dag_id,
            "source_path": str(file_path),
            "source_files": source_files,
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
        self,
        module_name: str,
        meta: DagMeta,
        file_path: Path,
        now: datetime.datetime,
        source_files: list[str],
    ) -> Asset:
        native_id = meta.dag_id or module_name
        qualified_name, identity_key = airflow_extraction_identity(native_id)
        existing = self._store.find_by_identity(PROVIDER, identity_key)
        attributes = {
            "dag_id": meta.dag_id,
            "module_name": module_name,
            "source_path": str(file_path),
            "source_files": source_files,
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


def _lineage_mode(settings: DwhCollectorSettings) -> str:
    mode = (settings.airflow_lineage_mode or "catalog").strip().lower()
    return mode if mode in {"catalog", "code"} else "catalog"


def _relative_sources(paths: list[str | None], root: Path) -> list[str]:
    found: list[str] = []
    seen: set[str] = set()
    for raw in paths:
        if not raw:
            continue
        rel = _relative_to_root(raw, root)
        if rel in seen:
            continue
        seen.add(rel)
        found.append(rel)
    return found


def _relative_to_root(raw: str, root: Path) -> str:
    path = Path(raw)
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _merge_source_files(existing: Any, incoming: list[str]) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    for item in list(existing or []) + incoming:
        text = str(item).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        merged.append(text)
    return merged


def _module_name(file_path: Path, root: Path) -> str:
    try:
        relative = file_path.resolve().relative_to(root.resolve())
    except ValueError:
        return file_path.stem
    return relative.with_suffix("").as_posix()


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
