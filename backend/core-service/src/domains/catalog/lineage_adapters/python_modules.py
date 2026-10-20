"""AST lineage for extraction_registry PROCESS modules. Never import loaders."""

from __future__ import annotations

import datetime
from pathlib import Path
from typing import Any

from domains.catalog.identity import storage_location_identity, unresolved_target_identity
from domains.catalog.lineage_adapters.airflow_dags import (
    MAX_FILE_BYTES,
    SKIP_DIRS,
    UNQUALIFIED_STOPLIST,
)
from domains.catalog.lineage_adapters.airflow_syntax import (
    TableRef,
    bind_imported_constants,
    dag_closure,
    iter_local_deps,
    parse_module,
    rescan_writes,
    resolve_local_module,
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
    DiscoveryDiagnostic,
    LineageStatus,
    MetadataStatus,
    Relationship,
    RelationshipType,
)
from domains.catalog.repositories.ports import PortalStore
from settings.portal import DwhCollectorSettings

PROVIDER = "python_modules"
REGISTRY_PROVIDER = "extraction_registry"
WRITE_TYPES = {AssetType.TABLE, AssetType.MATERIALIZED_VIEW}
PYTHON_HANDLERS = frozenset({"Python", "PythonV0"})


class PythonModulesLineageAdapter:
    """Attach WRITES_TO to registry PROCESS assets by scanning module sources."""

    name = "python_modules"

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
        root_raw = (self._settings.python_modules_root or "").strip()
        if not root_raw:
            return skipped_run(
                self._store,
                name=self.name,
                started=started,
                reason="MODULES_ROOT_MISSING",
                message="Python modules root is not configured",
            )
        root = Path(root_raw)
        if not root.is_dir():
            return skipped_run(
                self._store,
                name=self.name,
                started=started,
                reason="MODULES_ROOT_MISSING",
                message=f"Python modules root does not exist: {root}",
            )
        mode = _lineage_mode(self._settings)
        details = {
            "processes": 0,
            "resolved": 0,
            "writes": 0,
            "storages": 0,
            "unresolved": 0,
            "diagnostics": 0,
            "mode": mode,
        }
        try:
            catalog_tables = self._catalog_write_targets()
            processes = self._registry_python_processes()
            details["processes"] = len(processes)
            facts_cache: dict[Path, Any] = {}
            for process in processes:
                self._ingest_process(
                    process, root, catalog_tables, facts_cache, started, mode, details
                )
            message = (
                f"Scanned {details['processes']} processes, "
                f"resolved {details['resolved']}, writes {details['writes']}"
            )
            status = (
                CollectorStatus.PARTIAL
                if details["diagnostics"] and details["writes"]
                else CollectorStatus.SUCCESS
            )
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

    def _registry_python_processes(self) -> list[Asset]:
        assets, _ = self._store.list_assets(
            AssetQuery(status=AssetStatus.ACTIVE, page=1, page_size=10_000)
        )
        result: list[Asset] = []
        for item in assets:
            if item.asset_type != AssetType.PROCESS:
                continue
            if item.source_provider != REGISTRY_PROVIDER:
                continue
            handler = str(item.attributes.get("handler_type") or "")
            if handler not in PYTHON_HANDLERS:
                continue
            if not item.attributes.get("module"):
                continue
            result.append(item)
        return result

    def _catalog_write_targets(self) -> list[Asset]:
        assets, _ = self._store.list_assets(
            AssetQuery(status=AssetStatus.ACTIVE, page=1, page_size=10_000)
        )
        return [item for item in assets if item.asset_type in WRITE_TYPES]

    def _ingest_process(
        self,
        process: Asset,
        root: Path,
        catalog_tables: list[Asset],
        facts_cache: dict[Path, Any],
        now: datetime.datetime,
        mode: str,
        details: dict,
    ) -> None:
        module_name = str(process.attributes.get("module") or "").strip()
        entry = resolve_local_module(module_name, root / "_portal_entry_.py", root)
        if entry is None:
            details["diagnostics"] += 1
            self._diagnostic(
                process.id,
                now,
                {
                    "code": "MODULE_FILE_MISSING",
                    "message": f"module {module_name!r} not found under python modules root",
                    "module": module_name,
                },
            )
            self._mark_process(process, MetadataStatus.MISSING, LineageStatus.UNRESOLVED, now)
            return

        closure_paths = self._ensure_closure(entry, root, facts_cache)
        has_write = any(
            facts_cache[path].has_write for path in closure_paths if path in facts_cache
        )
        refs = write_targets_for_closure(closure_paths, facts_cache) if has_write else []
        matched = self._match_tables(refs, catalog_tables, now, mode, root)
        path_refs = storage_paths_for_closure(closure_paths, facts_cache) if mode == "code" else []

        if not matched and not path_refs:
            details["diagnostics"] += 1
            self._diagnostic(
                process.id,
                now,
                {
                    "code": "NO_WRITE_TARGETS",
                    "message": f"no write targets found in module closure for {module_name}",
                    "module": module_name,
                    "entry": str(entry),
                },
            )
            self._mark_process(process, MetadataStatus.MISSING, LineageStatus.UNRESOLVED, now)
            return

        unresolved = 0
        for table in matched:
            self._rel(process.id, table.id, RelationshipType.WRITES_TO)
            details["writes"] += 1
            if table.attributes.get("unresolved"):
                unresolved += 1
                details["unresolved"] += 1
        for path_ref in path_refs:
            storage = self._upsert_storage(path_ref.path, now)
            self._rel(process.id, storage.id, RelationshipType.READS_FROM)
            details["storages"] += 1

        lineage = (
            LineageStatus.PARTIAL
            if unresolved
            else LineageStatus.RESOLVED
            if matched
            else LineageStatus.UNRESOLVED
        )
        self._mark_process(process, MetadataStatus.OK, lineage, now, source_files=_rel_files(closure_paths, root))
        details["resolved"] += 1

    def _ensure_closure(
        self, entry: Path, root: Path, facts_cache: dict[Path, Any]
    ) -> list[Path]:
        resolved_root = root.resolve()
        queue = [entry.resolve()]
        seen: set[Path] = set()
        while queue:
            path = queue.pop(0)
            if path in seen:
                continue
            seen.add(path)
            if path not in facts_cache:
                facts = self._parse_file(path)
                if facts is None:
                    continue
                facts_cache[path] = facts
            for dep in iter_local_deps(facts_cache[path], resolved_root):
                if dep not in seen:
                    queue.append(dep)
        bind_imported_constants(facts_cache, resolved_root)
        for facts in facts_cache.values():
            rescan_writes(facts)
        return dag_closure(entry.resolve(), facts_cache, resolved_root)

    def _parse_file(self, path: Path) -> Any | None:
        if any(part in SKIP_DIRS for part in path.parts):
            return None
        try:
            size = path.stat().st_size
        except OSError:
            return None
        if size > MAX_FILE_BYTES:
            return None
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return None
        return parse_module(path, text)

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

    def _upsert_storage(self, path: str, now: datetime.datetime) -> Asset:
        qualified_name, identity_key = storage_location_identity(path)
        existing = self._store.find_by_identity(PROVIDER, identity_key)
        if existing is None:
            existing = self._store.find_by_qualified_name(qualified_name)
        attributes = {"path": path, "origin": "python_modules", "display_name": path}
        if existing is not None:
            existing.last_seen_at = now
            existing.deleted_at = None
            existing.attributes = {**existing.attributes, **attributes}
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

    def _mark_process(
        self,
        process: Asset,
        metadata_status: MetadataStatus,
        lineage_status: LineageStatus,
        now: datetime.datetime,
        *,
        source_files: list[str] | None = None,
    ) -> None:
        process.last_seen_at = now
        attrs = dict(process.attributes)
        attrs["metadata_status"] = metadata_status
        attrs["lineage_status"] = lineage_status
        if source_files is not None:
            attrs["source_files"] = source_files
        process.attributes = attrs
        self._store.upsert_asset(process)

    def _rel(self, from_id, to_id, rel_type: RelationshipType) -> None:
        self._store.upsert_relationship(
            Relationship(
                from_asset_id=from_id,
                to_asset_id=to_id,
                relationship_type=rel_type,
                source_provider=PROVIDER,
            )
        )

    def _diagnostic(self, asset_id, now: datetime.datetime, payload: dict) -> None:
        self._store.add_diagnostic(
            DiscoveryDiagnostic(
                asset_id=asset_id,
                detected_at=now,
                severity="warning",
                code=str(payload.get("code") or "DIAGNOSTIC"),
                message=str(payload.get("message") or payload.get("code") or "diagnostic"),
                details=payload,
            )
        )


def _lineage_mode(settings: DwhCollectorSettings) -> str:
    mode = (settings.python_modules_lineage_mode or "catalog").strip().lower()
    return mode if mode in {"catalog", "code"} else "catalog"


def _rel_files(paths: list[Path], root: Path) -> list[str]:
    found: list[str] = []
    seen: set[str] = set()
    root_resolved = root.resolve()
    for path in paths:
        try:
            rel = str(path.resolve().relative_to(root_resolved))
        except ValueError:
            rel = str(path)
        if rel in seen:
            continue
        seen.add(rel)
        found.append(rel)
    return found
