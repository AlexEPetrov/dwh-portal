"""AST-only scan of Airflow DAG sources. Never import or execute DAG code."""

from __future__ import annotations

import ast
import re
import warnings
from dataclasses import dataclass, field
from pathlib import Path

MAX_CLOSURE = 80
SKIP_IMPORT_ROOTS = frozenset(
    {
        "airflow",
        "plugins",
        "shared",
        "sqlalchemy",
        "pandas",
        "numpy",
        "requests",
        "pydantic",
        "logging",
        "datetime",
        "pathlib",
        "json",
        "os",
        "sys",
        "re",
        "csv",
        "typing",
        "uuid",
        "http",
        "functools",
        "collections",
        "string",
        "io",
        "time",
        "math",
        "itertools",
        "copy",
        "abc",
        "enum",
        "dataclasses",
        "bs4",
        "lxml",
        "openpyxl",
        "selenium",
        "pendulum",
        "pytz",
        "psycopg2",
        "alembic",
    }
)
WRITE_FUNCS = frozenset(
    {
        "insert_to_db",
        "insert_values_to_db",
        "insert_batch_to_db",
        "save_to_db",
        "save_db",
        "upsert",
        "upsert_db",
        "to_sql",
        "CSVtoPostgresUpsert",
        "CSVtoPostgres",
        "on_conflict_do_update",
        "insert",
    }
)
WRITE_ATTRS = frozenset(
    {
        "to_sql",
        "on_conflict_do_update",
        "upsert",
        "bulk_insert_mappings",
        "bulk_save_objects",
    }
)
SESSION_OWNERS = frozenset({"session", "sess", "db_session", "connection", "conn"})
INSERT_OWNERS = frozenset({"postgresql", "sa", "sqlalchemy", "pg"})
SCHEMA_TABLE_KW = {
    "schema": "schema",
    "table": "table",
    "tablename": "table",
    "table_name": "table",
    "name": "table",
}
# (table_arg_index, schema_arg_index)
POSITIONAL_SCHEMA_TABLE = {
    "insert_to_db": (2, 1),
    "insert_values_to_db": (2, 1),
    "insert_batch_to_db": (2, 1),
    "save_to_db": (2, 1),
    "to_sql": (0, None),
}
_SQL_INTO = re.compile(
    r"(?i)\b(?:INSERT\s+INTO|UPDATE|MERGE\s+INTO|COPY)\s+([A-Za-z_][\w]*)\.([A-Za-z_][\w]*)"
)
_SQL_DML = re.compile(r"(?i)\b(?:INSERT|UPDATE|MERGE|COPY)\b")


@dataclass(frozen=True)
class DagMeta:
    dag_id: str | None = None
    description: str | None = None


@dataclass(frozen=True)
class TableRef:
    schema: str | None
    name: str
    source_path: str | None = None


@dataclass
class LoaderTableSpec:
    """Unresolved `_TABLE_NAME` / `_DB_SCHEMA` / `_TABLES_SCHEMA` declaration."""

    class_name: str | None
    bases: tuple[str, ...]
    table_kind: str | None
    table_value: str | None
    schema_kind: str | None
    schema_value: str | None
    aliases: dict[str, str]
    source_path: str
    table_keys: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class StoragePathRef:
    path: str
    source_path: str


@dataclass
class ModuleFacts:
    path: Path
    source: str
    is_dag: bool = False
    dag_meta: DagMeta = field(default_factory=DagMeta)
    constants: dict[str, str] = field(default_factory=dict)
    class_constants: dict[str, dict[str, str]] = field(default_factory=dict)
    class_bases: dict[str, tuple[str, ...]] = field(default_factory=dict)
    import_modules: list[str] = field(default_factory=list)
    import_from: list[tuple[str | None, int, list[str]]] = field(default_factory=list)
    classes: dict[str, TableRef] = field(default_factory=dict)
    adapters: dict[str, TableRef] = field(default_factory=dict)
    write_tables: list[TableRef] = field(default_factory=list)
    sql_tables: list[TableRef] = field(default_factory=list)
    call_tables: list[TableRef] = field(default_factory=list)
    loader_specs: list[LoaderTableSpec] = field(default_factory=list)
    write_classes: set[str] = field(default_factory=set)
    write_adapters: set[str] = field(default_factory=set)
    storage_paths: list[str] = field(default_factory=list)
    has_write: bool = False
    imported_names: dict[str, tuple[str, str]] = field(default_factory=dict)


def _parse_source(text: str, filename: str) -> ast.AST:
    """Parse DAG text. Invalid regex escapes in non-raw strings are a DAG-source
    problem, not a collector failure — do not spam collect logs."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", SyntaxWarning)
        return ast.parse(text, filename=filename)


def _is_name_eq_main(node: ast.AST) -> bool:
    if not isinstance(node, ast.Compare) or len(node.ops) != 1:
        return False
    if not isinstance(node.ops[0], ast.Eq) or len(node.comparators) != 1:
        return False
    left, right = node.left, node.comparators[0]

    def is_name(item: ast.AST) -> bool:
        return isinstance(item, ast.Name) and item.id == "__name__"

    def is_main(item: ast.AST) -> bool:
        return isinstance(item, ast.Constant) and item.value == "__main__"

    return (is_name(left) and is_main(right)) or (is_main(left) and is_name(right))


def _is_main_guard(test: ast.AST) -> bool:
    if _is_name_eq_main(test):
        return True
    if isinstance(test, ast.BoolOp):
        return any(_is_name_eq_main(value) for value in test.values)
    return False


def _walk_code(tree: ast.AST):
    """Walk the module AST, skipping `if __name__ == '__main__'` and its body."""
    skipped: set[int] = set()
    body = tree.body if isinstance(tree, ast.Module) else []
    for stmt in body:
        if isinstance(stmt, ast.If) and _is_main_guard(stmt.test):
            for child in ast.walk(stmt):
                skipped.add(id(child))
    for node in ast.walk(tree):
        if id(node) in skipped:
            continue
        yield node


def parse_module(path: Path, text: str) -> ModuleFacts | None:
    try:
        tree = _parse_source(text, str(path))
    except SyntaxError:
        return None
    facts = ModuleFacts(path=path, source=text)
    facts.constants = _assign_constants(tree)
    _scan_class_scopes(tree, facts)
    _scan_imports(tree, facts)
    _scan_orm_classes(tree, facts)
    _scan_loader_tables(tree, facts)
    _scan_adapter_assigns(tree, facts)
    _scan_writes(tree, facts)
    facts.is_dag = _is_dag_module(tree)
    if facts.is_dag:
        facts.dag_meta = _dag_meta_from_ast(tree)
    return facts


def bind_imported_constants(
    facts_by_path: dict[Path, ModuleFacts], root: Path
) -> None:
    for facts in facts_by_path.values():
        for alias, (module, orig) in facts.imported_names.items():
            if alias in facts.constants:
                continue
            resolved = resolve_local_module(module, facts.path, root)
            if resolved is None:
                continue
            other = facts_by_path.get(resolved) or facts_by_path.get(resolved.resolve())
            if other is None:
                continue
            if orig in other.constants:
                facts.constants[alias] = other.constants[orig]


def rescan_writes(facts: ModuleFacts) -> None:
    try:
        tree = _parse_source(facts.source, str(facts.path))
    except SyntaxError:
        return
    facts.write_tables.clear()
    facts.sql_tables.clear()
    facts.call_tables.clear()
    facts.write_classes.clear()
    facts.write_adapters.clear()
    facts.storage_paths.clear()
    facts.has_write = False
    _scan_writes(tree, facts)


def resolve_local_module(spec: str, from_file: Path, root: Path) -> Path | None:
    if not spec or spec.startswith("."):
        return None
    first = spec.split(".", 1)[0]
    if first in SKIP_IMPORT_ROOTS:
        return None
    parts = spec.split(".")
    if parts[0] == "dags" and not (root / "dags").is_dir():
        parts = parts[1:]
    if not parts:
        return None
    candidate = root.joinpath(*parts)
    py_file = candidate.with_suffix(".py")
    if py_file.is_file() and _under_root(py_file, root):
        return py_file.resolve()
    init = candidate / "__init__.py"
    if init.is_file() and _under_root(init, root):
        return init.resolve()
    return None


def resolve_relative(module: str | None, level: int, from_file: Path, root: Path) -> Path | None:
    base = from_file.parent
    for _ in range(max(level - 1, 0)):
        base = base.parent
    if module:
        base = base.joinpath(*module.split("."))
        py_file = base.with_suffix(".py")
        if py_file.is_file() and _under_root(py_file, root):
            return py_file.resolve()
    init = base / "__init__.py"
    if init.is_file() and _under_root(init, root):
        return init.resolve()
    return None


def iter_local_deps(facts: ModuleFacts, root: Path) -> list[Path]:
    found: list[Path] = []
    for spec in facts.import_modules:
        resolved = resolve_local_module(spec, facts.path, root)
        if resolved is not None:
            found.append(resolved)
    for module, level, names in facts.import_from:
        if level:
            if module:
                resolved = resolve_relative(module, level, facts.path, root)
                if resolved is not None:
                    found.append(resolved)
            else:
                for name in names:
                    resolved = resolve_relative(name, level, facts.path, root)
                    if resolved is not None:
                        found.append(resolved)
            continue
        if module:
            resolved = resolve_local_module(module, facts.path, root)
            if resolved is not None:
                found.append(resolved)
            for name in names:
                nested = resolve_local_module(f"{module}.{name}", facts.path, root)
                if nested is not None:
                    found.append(nested)
    return found


def dag_closure(
    start: Path, facts_by_path: dict[Path, ModuleFacts], root: Path
) -> list[Path]:
    seen: list[Path] = []
    queue = [start]
    queued = {start}
    while queue and len(seen) < MAX_CLOSURE:
        current = queue.pop(0)
        seen.append(current)
        facts = facts_by_path.get(current)
        if facts is None:
            continue
        for dep in iter_local_deps(facts, root):
            if dep in queued:
                continue
            queued.add(dep)
            queue.append(dep)
    return seen


def write_targets_for_closure(
    closure: list[Path], facts_by_path: dict[Path, ModuleFacts]
) -> list[TableRef]:
    from domains.catalog.lineage_adapters.table_target_pipes import first_table_targets

    return first_table_targets(closure, facts_by_path)


def storage_paths_for_closure(
    closure: list[Path], facts_by_path: dict[Path, ModuleFacts]
) -> list[StoragePathRef]:
    found: list[StoragePathRef] = []
    seen: set[str] = set()
    for path in closure:
        facts = facts_by_path.get(path)
        if facts is None:
            continue
        origin = str(facts.path)
        for raw in facts.storage_paths:
            key = raw.lower()
            if key in seen:
                continue
            seen.add(key)
            found.append(StoragePathRef(path=raw, source_path=origin))
    return found


def _under_root(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _const_str(node: ast.AST | None) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _joined_str(
    node: ast.JoinedStr,
    constants: dict[str, str],
    facts: ModuleFacts | None = None,
    enclosing: str | None = None,
) -> str | None:
    parts: list[str] = []
    for value in node.values:
        if isinstance(value, ast.Constant) and isinstance(value.value, str):
            parts.append(value.value)
            continue
        if isinstance(value, ast.FormattedValue):
            resolved = _resolve_expr(value.value, constants, facts, enclosing)
            if resolved is None:
                return None
            parts.append(resolved)
            continue
        return None
    return "".join(parts)


def _partial_sql_fstring(
    node: ast.JoinedStr,
    constants: dict[str, str],
    facts: ModuleFacts | None = None,
    enclosing: str | None = None,
) -> str | None:
    """Substitute known strings and blank the rest for SQL table matching.

    A hole is known when it is a literal, a module constant, or a class
    attribute (``cls.TABLE``, ``self.TABLE``, ``ClassName.TABLE``) bound to a
    string. Other holes become ``?`` and cannot be read as an identifier.
    """
    parts: list[str] = []
    substituted = False
    for value in node.values:
        if isinstance(value, ast.Constant) and isinstance(value.value, str):
            parts.append(value.value)
            continue
        if isinstance(value, ast.FormattedValue):
            resolved = _resolve_expr(value.value, constants, facts, enclosing)
            if resolved is None:
                parts.append("?")
                continue
            parts.append(resolved)
            substituted = True
            continue
        return None
    if not substituted:
        return None
    return "".join(parts)


def _assign_constants(tree: ast.AST) -> dict[str, str]:
    body = tree.body if isinstance(tree, ast.Module) else []
    return _constants_from_statements(body, {})


def _constants_from_statements(
    statements: list[ast.stmt], known: dict[str, str]
) -> dict[str, str]:
    constants: dict[str, str] = {}
    for stmt in statements:
        if isinstance(stmt, ast.Assign) and isinstance(stmt.value, ast.Tuple):
            names, values = _tuple_assign(stmt)
            resolved_values = [_bound_string(item, known) for item in values]
            if not names or any(item is None for item in resolved_values):
                continue
            for name, resolved in zip(names, resolved_values, strict=False):
                if resolved is not None:
                    constants[name] = resolved
            continue
        if isinstance(stmt, ast.Assign):
            resolved = _bound_string(stmt.value, known)
            if resolved is None:
                continue
            for target in stmt.targets:
                if isinstance(target, ast.Name):
                    constants[target.id] = resolved
            continue
        target, value = _assign_target_value(stmt)
        if target is None or value is None:
            continue
        resolved = _bound_string(value, known)
        if resolved is not None:
            constants[target] = resolved
    return constants


def _tuple_assign(stmt: ast.stmt) -> tuple[list[str], list[ast.AST]]:
    if not isinstance(stmt, ast.Assign) or not isinstance(stmt.value, ast.Tuple):
        return [], []
    names: list[str] = []
    for target in stmt.targets:
        if isinstance(target, ast.Tuple):
            names = [elt.id for elt in target.elts if isinstance(elt, ast.Name)]
    return names, list(stmt.value.elts)


def _bound_string(node: ast.AST, known: dict[str, str]) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Name):
        return known.get(node.id)
    return None


def _scan_class_scopes(tree: ast.AST, facts: ModuleFacts) -> None:
    body = tree.body if isinstance(tree, ast.Module) else []
    for node in body:
        if not isinstance(node, ast.ClassDef):
            continue
        bases = tuple(name for name in (_base_name(base) for base in node.bases) if name)
        facts.class_bases[node.name] = bases
        constants = _constants_from_statements(node.body, facts.constants)
        if constants:
            facts.class_constants[node.name] = constants


def _scan_imports(tree: ast.AST, facts: ModuleFacts) -> None:
    for node in _walk_code(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                facts.import_modules.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            names = [alias.name for alias in node.names if alias.name != "*"]
            facts.import_from.append((node.module, node.level or 0, names))
            if node.module:
                for alias in node.names:
                    local = alias.asname or alias.name
                    facts.imported_names[local] = (node.module, alias.name)


def _scan_orm_classes(tree: ast.AST, facts: ModuleFacts) -> None:
    for node in tree.body if isinstance(tree, ast.Module) else []:
        if not isinstance(node, ast.ClassDef):
            continue
        table_name: str | None = None
        schema: str | None = None
        for stmt in node.body:
            if not isinstance(stmt, ast.Assign):
                continue
            targets = [t.id for t in stmt.targets if isinstance(t, ast.Name)]
            if "__tablename__" in targets:
                table_name = _resolve_str(stmt.value, facts.constants)
            if "__table_args__" in targets:
                schema = _schema_from_table_args(stmt.value, facts.constants) or schema
        if table_name:
            facts.classes[node.name] = TableRef(
                schema=schema, name=table_name, source_path=str(facts.path)
            )


def _scan_loader_tables(tree: ast.AST, facts: ModuleFacts) -> None:
    body = tree.body if isinstance(tree, ast.Module) else []
    module_spec = _loader_spec_from_statements(None, (), body, str(facts.path))
    if module_spec is not None:
        facts.loader_specs.append(module_spec)
    for node in body:
        if not isinstance(node, ast.ClassDef):
            continue
        bases = tuple(_base_name(base) for base in node.bases)
        bases = tuple(name for name in bases if name)
        spec = _loader_spec_from_statements(node.name, bases, node.body, str(facts.path))
        if spec is not None:
            facts.loader_specs.append(spec)


def _base_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _loader_spec_from_statements(
    class_name: str | None,
    bases: tuple[str, ...],
    statements: list[ast.stmt],
    source_path: str,
) -> LoaderTableSpec | None:
    aliases: dict[str, str] = {}
    table_kind: str | None = None
    table_value: str | None = None
    schema_kind: str | None = None
    schema_value: str | None = None
    table_keys: list[tuple[str, str]] = []
    saw = False
    for stmt in statements:
        target, value = _assign_target_value(stmt)
        if target is None or value is None:
            continue
        if target == "_TABLES_SCHEMA" and isinstance(value, ast.Dict):
            saw = True
            table_keys = _dict_table_keys(value)
            continue
        if target not in {"_TABLE_NAME", "_DB_SCHEMA"} and isinstance(value, ast.Name):
            aliases[target] = value.id
            continue
        kind, raw = _classify_loader_value(value)
        if target == "_TABLE_NAME":
            saw = True
            table_kind, table_value = kind, raw
        elif target == "_DB_SCHEMA":
            saw = True
            schema_kind, schema_value = kind, raw
    if not saw:
        return None
    return LoaderTableSpec(
        class_name=class_name,
        bases=bases,
        table_kind=table_kind,
        table_value=table_value,
        schema_kind=schema_kind,
        schema_value=schema_value,
        aliases=aliases,
        source_path=source_path,
        table_keys=tuple(table_keys),
    )


def _assign_target_value(stmt: ast.stmt) -> tuple[str | None, ast.AST | None]:
    if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1 and isinstance(stmt.targets[0], ast.Name):
        return stmt.targets[0].id, stmt.value
    if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name) and stmt.value is not None:
        return stmt.target.id, stmt.value
    return None, None


def _dict_table_keys(node: ast.Dict) -> list[tuple[str, str]]:
    keys: list[tuple[str, str]] = []
    for key in node.keys:
        if key is None:
            continue
        kind, raw = _classify_loader_value(key)
        if kind in {"str", "name"} and raw:
            keys.append((kind, raw))
    return keys


def _classify_loader_value(value: ast.AST) -> tuple[str, str | None]:
    if isinstance(value, ast.Constant):
        if isinstance(value.value, str):
            return "str", value.value
        if value.value is None:
            return "none", None
        return "unknown", None
    if isinstance(value, ast.Name):
        return "name", value.id
    if (
        isinstance(value, ast.Attribute)
        and value.attr == "__tablename__"
        and isinstance(value.value, ast.Name)
    ):
        return "tablename", value.value.id
    if isinstance(value, ast.Subscript) and isinstance(value.value, ast.Attribute):
        owner = value.value
        key = value.slice
        if (
            owner.attr == "__table_args__"
            and isinstance(owner.value, ast.Name)
            and isinstance(key, ast.Constant)
            and key.value == "schema"
        ):
            return "table_args", owner.value.id
    return "unknown", None


def _schema_from_table_args(node: ast.AST, constants: dict[str, str]) -> str | None:
    dict_nodes: list[ast.Dict] = []
    if isinstance(node, ast.Dict):
        dict_nodes.append(node)
    elif isinstance(node, ast.Tuple):
        dict_nodes.extend(elt for elt in node.elts if isinstance(elt, ast.Dict))
    for item in dict_nodes:
        for key, value in zip(item.keys, item.values, strict=True):
            if _const_str(key) == "schema":
                return _resolve_str(value, constants)
    return None


def _scan_adapter_assigns(tree: ast.AST, facts: ModuleFacts) -> None:
    for node in _walk_code(tree):
        if not isinstance(node, ast.Assign):
            continue
        root = node.value
        while isinstance(root, ast.Call) and isinstance(root.func, ast.Attribute):
            root = root.func.value
        if not isinstance(root, ast.Call) or _call_name(root.func) != "DbModelAdapter":
            continue
        if len(root.args) < 3:
            continue
        table = _resolve_str(root.args[1], facts.constants)
        schema = _resolve_str(root.args[2], facts.constants)
        if not table:
            continue
        ref = TableRef(schema=schema, name=table, source_path=str(facts.path))
        for target in node.targets:
            if isinstance(target, ast.Name):
                facts.adapters[target.id] = ref


def _scan_writes(tree: ast.AST, facts: ModuleFacts) -> None:
    constructors: set[str] = set()
    known = set(facts.classes) | set(facts.imported_names)
    parents = _parent_map(tree)
    for node in _walk_code(tree):
        if not isinstance(node, ast.Call):
            continue
        func_name = _call_name(node.func)
        attr_name = _call_attr(node.func)
        owner = _attr_owner(node.func)
        if func_name in WRITE_FUNCS or attr_name in WRITE_ATTRS:
            facts.has_write = True
            _tables_from_call(node, func_name, facts, _enclosing_class(node, parents))
        if attr_name == "insert" and owner in INSERT_OWNERS:
            facts.has_write = True
        if attr_name in {"merge", "add", "add_all"} and _is_session_owner(owner):
            facts.has_write = True
            class_name = _class_from_arg(node.args[0] if node.args else None)
            if class_name:
                facts.write_classes.add(class_name)
        if func_name in {"upsert", "upsert_db"} or attr_name in {"upsert", "upsert_db"}:
            facts.has_write = True
            for arg in node.args:
                class_name = _class_from_arg(arg)
                if class_name:
                    facts.write_classes.add(class_name)
            if owner:
                facts.write_adapters.add(owner)
        if isinstance(node.func, ast.Name) and node.func.id in known:
            constructors.add(node.func.id)
    _scan_sql_literals(tree, facts, parents)
    if facts.has_write:
        facts.write_classes.update(constructors)


def _is_session_owner(name: str | None) -> bool:
    if not name:
        return False
    lowered = name.lower()
    return lowered in SESSION_OWNERS or "session" in lowered


def _scan_sql_literals(
    tree: ast.AST, facts: ModuleFacts, parents: dict[int, ast.AST] | None = None
) -> None:
    parent_of = parents if parents is not None else _parent_map(tree)
    for node in _walk_code(tree):
        text: str | None = None
        enclosing = _enclosing_class(node, parent_of)
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            text = node.value
        elif isinstance(node, ast.JoinedStr):
            text = _joined_str(node, facts.constants, facts, enclosing)
            if text is None:
                partial = _partial_sql_fstring(node, facts.constants, facts, enclosing)
                if partial:
                    _sql_from_text(partial, facts)
                continue
        if not text:
            continue
        _sql_from_text(text, facts)
        if _looks_like_storage_path(text):
            facts.storage_paths.append(text.strip())


def _tables_from_call(
    node: ast.Call,
    func_name: str | None,
    facts: ModuleFacts,
    enclosing: str | None = None,
) -> None:
    schema: str | None = None
    table: str | None = None

    def resolve(value: ast.AST) -> str | None:
        return _resolve_str(value, facts.constants, facts, enclosing)

    for keyword in node.keywords:
        role = SCHEMA_TABLE_KW.get(keyword.arg or "")
        if role == "schema":
            schema = resolve(keyword.value)
        elif role == "table":
            table = resolve(keyword.value)
    positions = POSITIONAL_SCHEMA_TABLE.get(func_name or "")
    if positions:
        name_i, schema_i = positions[0], positions[1]
        if table is None and name_i is not None and name_i < len(node.args):
            table = resolve(node.args[name_i])
        if schema is None and schema_i is not None and schema_i < len(node.args):
            schema = resolve(node.args[schema_i])
        if func_name == "to_sql" and table is None and node.args:
            table = resolve(node.args[0])
    if table:
        ref = TableRef(schema=schema, name=table, source_path=str(facts.path))
        facts.call_tables.append(ref)
        facts.write_tables.append(ref)


def _sql_from_text(text: str | None, facts: ModuleFacts) -> None:
    if not text:
        return
    if _SQL_DML.search(text):
        facts.has_write = True
    for match in _SQL_INTO.finditer(text):
        facts.has_write = True
        ref = TableRef(schema=match.group(1), name=match.group(2), source_path=str(facts.path))
        facts.sql_tables.append(ref)
        facts.write_tables.append(ref)


_HTTP_URL = re.compile(r"(?i)^https?://")
_SQL_START = re.compile(r"(?i)^\s*(?:SELECT|INSERT|UPDATE|DELETE|WITH|CREATE|MERGE|COPY|ALTER)\b")
_STORAGE_URI = re.compile(r"(?i)^(?:s3|gs|abfss|wasbs|file|hdfs)://")
_WIN_PATH = re.compile(r"^[A-Za-z]:[\\/]")
_WEB_PREFIXES = (
    "/content/",
    "/static/",
    "/assets/",
    "/img/",
    "/images/",
    "/css/",
    "/js/",
    "/media/",
    "/fonts/",
    "/public/",
    "/dist/",
    "/build/",
    "/favicon",
    "/scripts/",
    "/styles/",
    "/vendor/",
)
_WEB_EXT = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".svg",
    ".ico",
    ".webp",
    ".css",
    ".js",
    ".mjs",
    ".woff",
    ".woff2",
    ".ttf",
    ".eot",
    ".map",
    ".html",
    ".htm",
}
_DATA_EXT = {
    ".csv",
    ".parquet",
    ".json",
    ".jsonl",
    ".ndjson",
    ".xml",
    ".xlsx",
    ".xls",
    ".zip",
    ".gz",
    ".tsv",
    ".txt",
    ".orc",
    ".avro",
    ".pkl",
    ".feather",
}
_POSIX_ROOTS = (
    "/data/",
    "/mnt/",
    "/opt/",
    "/var/",
    "/tmp/",
    "/home/",
    "/app/",
    "/srv/",
    "/warehouse/",
    "/datalake/",
)
_DATA_HINTS = (
    "landing",
    "airflow_files",
    "warehouse",
    "datalake",
    "/raw/",
    "/staging/",
    "/bronze/",
    "/silver/",
    "/extract",
    "/inbox",
    "/outbox",
)


def _looks_like_storage_path(text: str) -> bool:
    value = text.strip()
    if len(value) < 4 or len(value) > 512:
        return False
    if _HTTP_URL.match(value) or _SQL_START.match(value):
        return False
    if "\n" in value or "?" in value or "#" in value:
        return False
    lowered = value.lower().replace("\\", "/")
    if any(lowered.startswith(prefix) or lowered.startswith(prefix.rstrip("/")) for prefix in _WEB_PREFIXES):
        return False
    first_seg = "/" + lowered.lstrip("/").split("/", 1)[0] + "/"
    if first_seg in _WEB_PREFIXES:
        return False
    ext = Path(value.split("?")[0]).suffix.lower()
    if _STORAGE_URI.match(value):
        return True
    if _WIN_PATH.match(value) or value.startswith("\\\\"):
        return any(hint in lowered for hint in _DATA_HINTS) or ext in _DATA_EXT
    if not value.startswith("/"):
        return False
    if ext in _WEB_EXT:
        return False
    if any(lowered.startswith(root) for root in _POSIX_ROOTS):
        return True
    if any(hint in lowered for hint in _DATA_HINTS):
        return True
    return ext in _DATA_EXT and value.count("/") >= 2


def _class_from_arg(node: ast.AST | None) -> str | None:
    if node is None:
        return None
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _call_name(func: ast.AST) -> str | None:
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def _call_attr(func: ast.AST) -> str | None:
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def _attr_owner(func: ast.AST) -> str | None:
    if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
        return func.value.id
    return None


def _resolve_str(
    node: ast.AST | None,
    constants: dict[str, str],
    facts: ModuleFacts | None = None,
    enclosing: str | None = None,
) -> str | None:
    if node is None:
        return None
    direct = _const_str(node)
    if direct is not None:
        return direct
    if isinstance(node, ast.Name):
        return constants.get(node.id)
    if isinstance(node, ast.Attribute):
        return _resolve_class_attr(node, facts, enclosing)
    if isinstance(node, ast.JoinedStr):
        return _joined_str(node, constants, facts, enclosing)
    return None


def _resolve_expr(
    node: ast.AST,
    constants: dict[str, str],
    facts: ModuleFacts | None,
    enclosing: str | None,
) -> str | None:
    return _resolve_str(node, constants, facts, enclosing)


def _resolve_class_attr(
    node: ast.Attribute, facts: ModuleFacts | None, enclosing: str | None
) -> str | None:
    if facts is None or not isinstance(node.value, ast.Name):
        return None
    owner = node.value.id
    if owner in {"cls", "self"}:
        class_name = enclosing
    elif owner in facts.class_constants or owner in facts.class_bases:
        class_name = owner
    else:
        return None
    if class_name is None:
        return None
    return _lookup_class_attr(facts, class_name, node.attr)


def _lookup_class_attr(facts: ModuleFacts, class_name: str, attr: str) -> str | None:
    seen: set[str] = set()
    queue = [class_name]
    while queue:
        current = queue.pop(0)
        if not current or current in seen:
            continue
        seen.add(current)
        value = facts.class_constants.get(current, {}).get(attr)
        if value is not None:
            return value
        queue.extend(facts.class_bases.get(current, ()))
    return None


def _parent_map(tree: ast.AST) -> dict[int, ast.AST]:
    parents: dict[int, ast.AST] = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parents[id(child)] = node
    return parents


def _enclosing_class(node: ast.AST, parents: dict[int, ast.AST]) -> str | None:
    current = parents.get(id(node))
    while current is not None:
        if isinstance(current, ast.ClassDef):
            return current.name
        current = parents.get(id(current))
    return None


def _is_dag_module(tree: ast.AST) -> bool:
    for node in _walk_code(tree):
        if isinstance(node, ast.Call) and _call_name(node.func) in {"DAG", "dag"}:
            return True
        if isinstance(node, ast.FunctionDef):
            for dec in node.decorator_list:
                if isinstance(dec, ast.Name) and dec.id == "dag":
                    return True
                if isinstance(dec, ast.Call) and _call_name(dec.func) == "dag":
                    return True
    return False


def _dag_meta_from_ast(tree: ast.AST) -> DagMeta:
    for node in _walk_code(tree):
        if not isinstance(node, ast.Call) or _call_name(node.func) not in {"DAG", "dag"}:
            continue
        dag_id = None
        description = None
        if node.args:
            dag_id = _const_str(node.args[0])
        for keyword in node.keywords:
            if keyword.arg == "dag_id":
                dag_id = _const_str(keyword.value) or dag_id
            elif keyword.arg == "description":
                description = _const_str(keyword.value)
        if description:
            description = " ".join(description.split())
        return DagMeta(dag_id=dag_id, description=description or None)
    return DagMeta()
