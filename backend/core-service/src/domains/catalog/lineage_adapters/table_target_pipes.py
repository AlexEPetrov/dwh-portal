"""Sequential pipes that name a write target. The first pipe with a table wins."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from pathlib import Path

from domains.catalog.lineage_adapters.airflow_syntax import (
    LoaderTableSpec,
    ModuleFacts,
    TableRef,
)


class TableTargetContext:
    def __init__(self, closure: list[Path], facts_by_path: dict[Path, ModuleFacts]):
        self.closure = closure
        self.facts_by_path = facts_by_path
        self.class_tables: dict[str, TableRef] = {}
        self.adapter_tables: dict[str, TableRef] = {}
        self.specs_by_name: dict[str, LoaderTableSpec] = {}
        self._index()

    def _index(self) -> None:
        for facts in self._facts():
            self.class_tables.update(facts.classes)
            self.adapter_tables.update(facts.adapters)
            for spec in facts.loader_specs:
                if spec.class_name:
                    self.specs_by_name[spec.class_name] = spec
        for facts in self._facts():
            for alias, (_module, orig) in facts.imported_names.items():
                if orig in self.class_tables:
                    self.class_tables[alias] = self.class_tables[orig]
                if orig in self.adapter_tables:
                    self.adapter_tables[alias] = self.adapter_tables[orig]
                if orig in self.specs_by_name:
                    self.specs_by_name[alias] = self.specs_by_name[orig]

    def _facts(self) -> Iterable[ModuleFacts]:
        for path in self.closure:
            facts = self._facts_at(path)
            if facts is not None:
                yield facts

    def _facts_at(self, path: Path) -> ModuleFacts | None:
        facts = self.facts_by_path.get(path)
        if facts is not None:
            return facts
        resolved = path.resolve()
        for key, item in self.facts_by_path.items():
            if key.resolve() == resolved or item.path.resolve() == resolved:
                return item
        return None

    def has_write(self) -> bool:
        return any(facts.has_write for facts in self._facts())

    def entry(self) -> ModuleFacts | None:
        if not self.closure:
            return None
        return self._facts_at(self.closure[0])


def first_table_targets(
    closure: list[Path], facts_by_path: dict[Path, ModuleFacts]
) -> list[TableRef]:
    context = TableTargetContext(closure, facts_by_path)
    if not context.has_write():
        return []
    pipes: tuple[Callable[[TableTargetContext], list[TableRef]], ...] = (
        pipe_sql_text,
        pipe_call_arguments,
        pipe_loader_attributes,
        pipe_tables_schema,
        pipe_write_classes,
        pipe_orm_fallback,
    )
    for pipe in pipes:
        found = pipe(context)
        if found:
            return found
    return []


def pipe_sql_text(context: TableTargetContext) -> list[TableRef]:
    found: list[TableRef] = []
    for facts in context._facts():
        found.extend(facts.sql_tables)
    return _dedupe(found)


def pipe_call_arguments(context: TableTargetContext) -> list[TableRef]:
    found: list[TableRef] = []
    for facts in context._facts():
        found.extend(facts.call_tables)
    return _dedupe(found)


def pipe_loader_attributes(context: TableTargetContext) -> list[TableRef]:
    entry = context.entry()
    entry_path = entry.path if entry is not None else None
    own = [
        ref
        for facts in context._facts()
        if entry_path is not None and _same_path(facts.path, entry_path)
        for ref in _refs_from_facts(facts, context)
    ]
    if own:
        return _dedupe(own)
    found: list[TableRef] = []
    for facts in context._facts():
        found.extend(_refs_from_facts(facts, context))
    return _dedupe(found)


def pipe_tables_schema(context: TableTargetContext) -> list[TableRef]:
    entry = context.entry()
    entry_path = entry.path if entry is not None else None
    own = [
        ref
        for facts in context._facts()
        if entry_path is not None and _same_path(facts.path, entry_path)
        for ref in _tables_schema_refs(facts, context)
    ]
    if own:
        return _dedupe(own)
    found: list[TableRef] = []
    for facts in context._facts():
        found.extend(_tables_schema_refs(facts, context))
    return _dedupe(found)


def _tables_schema_refs(facts: ModuleFacts, context: TableTargetContext) -> list[TableRef]:
    refs: list[TableRef] = []
    for spec in facts.loader_specs:
        if not spec.table_keys:
            continue
        schema = _resolve_field(spec, "schema", context, set())
        for kind, raw in spec.table_keys:
            name = _resolve_kind(kind, raw, spec, context)
            if not name:
                continue
            refs.append(TableRef(schema=schema, name=name, source_path=spec.source_path))
    return refs


def pipe_write_classes(context: TableTargetContext) -> list[TableRef]:
    found: list[TableRef] = []
    for facts in context._facts():
        origin = str(facts.path)
        for class_name in facts.write_classes:
            found.append(_with_origin(context.class_tables.get(class_name), origin))
        for adapter_name in facts.write_adapters:
            found.append(_with_origin(context.adapter_tables.get(adapter_name), origin))
    return _dedupe(found)


def pipe_orm_fallback(context: TableTargetContext) -> list[TableRef]:
    found = list(context.class_tables.values()) + list(context.adapter_tables.values())
    return _dedupe(found)


def _refs_from_facts(facts: ModuleFacts, context: TableTargetContext) -> list[TableRef]:
    refs: list[TableRef] = []
    for spec in facts.loader_specs:
        ref = _resolve_loader_spec(spec, context)
        if ref is not None:
            refs.append(ref)
    return refs


def _resolve_loader_spec(spec: LoaderTableSpec, context: TableTargetContext) -> TableRef | None:
    if spec.table_kind == "none":
        return None
    table = _resolve_field(spec, "table", context, set())
    if not table:
        return None
    schema = _resolve_field(spec, "schema", context, set())
    return TableRef(schema=schema, name=table, source_path=spec.source_path)


def _resolve_field(
    spec: LoaderTableSpec,
    field_name: str,
    context: TableTargetContext,
    seen: set[str],
) -> str | None:
    marker = spec.class_name or spec.source_path
    if marker in seen:
        return None
    seen.add(marker)
    kind = spec.table_kind if field_name == "table" else spec.schema_kind
    raw = spec.table_value if field_name == "table" else spec.schema_value
    if kind == "none":
        return None
    if kind not in {None, "unknown"}:
        resolved = _resolve_kind(kind or "", raw, spec, context)
        if resolved:
            return resolved
        return None
    facts = _facts_for_spec(spec, context)
    for base in spec.bases:
        parent_name = base
        if facts is not None and base in facts.imported_names:
            parent_name = facts.imported_names[base][1]
        parent = context.specs_by_name.get(parent_name) or context.specs_by_name.get(base)
        if parent is None:
            continue
        found = _resolve_field(parent, field_name, context, seen)
        if found:
            return found
    return None


def _resolve_kind(
    kind: str,
    raw: str | None,
    spec: LoaderTableSpec,
    context: TableTargetContext,
) -> str | None:
    if kind == "str":
        return raw or None
    if kind == "name" and raw:
        return _constant(raw, spec, context)
    if kind == "tablename" and raw:
        ref = _class_ref(raw, spec, context)
        return ref.name if ref is not None else None
    if kind == "table_args" and raw:
        ref = _class_ref(raw, spec, context)
        return ref.schema if ref is not None else None
    return None


def _class_ref(
    name: str, spec: LoaderTableSpec, context: TableTargetContext
) -> TableRef | None:
    seen: set[str] = set()
    current: str | None = name
    while current and current not in seen:
        seen.add(current)
        ref = context.class_tables.get(current)
        if ref is not None:
            return ref
        current = spec.aliases.get(current)
    return None


def _constant(name: str, spec: LoaderTableSpec, context: TableTargetContext) -> str | None:
    facts = _facts_for_spec(spec, context)
    if facts is not None and name in facts.constants:
        return facts.constants[name]
    for item in context._facts():
        if name in item.constants:
            return item.constants[name]
    return None


def _facts_for_spec(spec: LoaderTableSpec, context: TableTargetContext) -> ModuleFacts | None:
    for facts in context._facts():
        if _same_path(facts.path, spec.source_path):
            return facts
    return None


def _with_origin(table: TableRef | None, origin: str) -> TableRef | None:
    if table is None or not table.name:
        return None
    return TableRef(
        schema=table.schema,
        name=table.name,
        source_path=table.source_path or origin,
    )


def _dedupe(tables: Iterable[TableRef | None]) -> list[TableRef]:
    found: list[TableRef] = []
    seen: set[tuple[str | None, str]] = set()
    for table in tables:
        if table is None or not table.name:
            continue
        key = (table.schema, table.name.lower())
        if key in seen:
            continue
        seen.add(key)
        found.append(table)
    return found


def _same_path(left: Path | str, right: Path | str) -> bool:
    try:
        return Path(left).resolve() == Path(right).resolve()
    except OSError:
        return str(left) == str(right)
