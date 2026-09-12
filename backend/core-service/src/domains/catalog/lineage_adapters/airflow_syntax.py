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


@dataclass
class ModuleFacts:
    path: Path
    source: str
    is_dag: bool = False
    dag_meta: DagMeta = field(default_factory=DagMeta)
    constants: dict[str, str] = field(default_factory=dict)
    import_modules: list[str] = field(default_factory=list)
    import_from: list[tuple[str | None, int, list[str]]] = field(default_factory=list)
    classes: dict[str, TableRef] = field(default_factory=dict)
    adapters: dict[str, TableRef] = field(default_factory=dict)
    write_tables: list[TableRef] = field(default_factory=list)
    write_classes: set[str] = field(default_factory=set)
    write_adapters: set[str] = field(default_factory=set)
    has_write: bool = False
    imported_names: dict[str, tuple[str, str]] = field(default_factory=dict)


def _parse_source(text: str, filename: str) -> ast.AST:
    """Parse DAG text. Invalid regex escapes in non-raw strings are a DAG-source
    problem, not a collector failure — do not spam collect logs."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", SyntaxWarning)
        return ast.parse(text, filename=filename)


def parse_module(path: Path, text: str) -> ModuleFacts | None:
    try:
        tree = _parse_source(text, str(path))
    except SyntaxError:
        return None
    facts = ModuleFacts(path=path, source=text)
    facts.constants = _assign_constants(tree)
    _scan_imports(tree, facts)
    _scan_orm_classes(tree, facts)
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
    facts.write_classes.clear()
    facts.write_adapters.clear()
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
    class_tables: dict[str, TableRef] = {}
    adapter_tables: dict[str, TableRef] = {}
    for path in closure:
        facts = facts_by_path.get(path)
        if facts is None:
            continue
        class_tables.update(facts.classes)
        adapter_tables.update(facts.adapters)
    for path in closure:
        facts = facts_by_path.get(path)
        if facts is None:
            continue
        for alias, (_module, orig) in facts.imported_names.items():
            if orig in class_tables:
                class_tables[alias] = class_tables[orig]
            if orig in adapter_tables:
                adapter_tables[alias] = adapter_tables[orig]
    found: list[TableRef] = []
    seen: set[tuple[str | None, str]] = set()

    def add(table: TableRef | None) -> None:
        if table is None or not table.name:
            return
        key = (table.schema, table.name.lower())
        if key in seen:
            return
        seen.add(key)
        found.append(table)

    for path in closure:
        facts = facts_by_path.get(path)
        if facts is None:
            continue
        for table in facts.write_tables:
            add(table)
        for class_name in facts.write_classes:
            add(class_tables.get(class_name))
        for adapter_name in facts.write_adapters:
            add(adapter_tables.get(adapter_name))
    if found:
        return found
    if any(
        facts_by_path[path].has_write
        for path in closure
        if path in facts_by_path
    ):
        for table in class_tables.values():
            add(table)
        for table in adapter_tables.values():
            add(table)
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


def _joined_str(node: ast.JoinedStr, constants: dict[str, str]) -> str | None:
    parts: list[str] = []
    for value in node.values:
        if isinstance(value, ast.Constant) and isinstance(value.value, str):
            parts.append(value.value)
            continue
        if isinstance(value, ast.FormattedValue) and isinstance(value.value, ast.Name):
            resolved = constants.get(value.value.id)
            if resolved is None:
                return None
            parts.append(resolved)
            continue
        return None
    return "".join(parts)


def _assign_constants(tree: ast.AST) -> dict[str, str]:
    constants: dict[str, str] = {}
    for node in tree.body if isinstance(tree, ast.Module) else []:
        if not isinstance(node, ast.Assign):
            continue
        value = node.value
        if isinstance(value, ast.Constant) and isinstance(value.value, str):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    constants[target.id] = value.value
            continue
        if isinstance(value, ast.Tuple) and all(
            isinstance(elt, ast.Constant) and isinstance(elt.value, str) for elt in value.elts
        ):
            names: list[str] = []
            for target in node.targets:
                if isinstance(target, ast.Tuple):
                    names = [elt.id for elt in target.elts if isinstance(elt, ast.Name)]
            for name, elt in zip(names, value.elts):
                constants[name] = str(elt.value)
    return constants


def _scan_imports(tree: ast.AST, facts: ModuleFacts) -> None:
    for node in ast.walk(tree):
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
            facts.classes[node.name] = TableRef(schema=schema, name=table_name)


def _schema_from_table_args(node: ast.AST, constants: dict[str, str]) -> str | None:
    dict_nodes: list[ast.Dict] = []
    if isinstance(node, ast.Dict):
        dict_nodes.append(node)
    elif isinstance(node, ast.Tuple):
        dict_nodes.extend(elt for elt in node.elts if isinstance(elt, ast.Dict))
    for item in dict_nodes:
        for key, value in zip(item.keys, item.values):
            if _const_str(key) == "schema":
                return _resolve_str(value, constants)
    return None


def _scan_adapter_assigns(tree: ast.AST, facts: ModuleFacts) -> None:
    for node in ast.walk(tree):
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
        ref = TableRef(schema=schema, name=table)
        for target in node.targets:
            if isinstance(target, ast.Name):
                facts.adapters[target.id] = ref


def _scan_writes(tree: ast.AST, facts: ModuleFacts) -> None:
    constructors: set[str] = set()
    known = set(facts.classes) | set(facts.imported_names)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func_name = _call_name(node.func)
        attr_name = _call_attr(node.func)
        owner = _attr_owner(node.func)
        if func_name in WRITE_FUNCS or attr_name in WRITE_ATTRS:
            facts.has_write = True
            _tables_from_call(node, func_name, facts)
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
    _scan_sql_literals(tree, facts)
    if facts.has_write:
        facts.write_classes.update(constructors)


def _is_session_owner(name: str | None) -> bool:
    if not name:
        return False
    lowered = name.lower()
    return lowered in SESSION_OWNERS or "session" in lowered


def _scan_sql_literals(tree: ast.AST, facts: ModuleFacts) -> None:
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            _sql_from_text(node.value, facts)
        elif isinstance(node, ast.JoinedStr):
            _sql_from_text(_joined_str(node, facts.constants), facts)


def _tables_from_call(node: ast.Call, func_name: str | None, facts: ModuleFacts) -> None:
    schema: str | None = None
    table: str | None = None
    for keyword in node.keywords:
        role = SCHEMA_TABLE_KW.get(keyword.arg or "")
        if role == "schema":
            schema = _resolve_str(keyword.value, facts.constants)
        elif role == "table":
            table = _resolve_str(keyword.value, facts.constants)
    positions = POSITIONAL_SCHEMA_TABLE.get(func_name or "")
    if positions:
        name_i, schema_i = positions[0], positions[1]
        if table is None and name_i is not None and name_i < len(node.args):
            table = _resolve_str(node.args[name_i], facts.constants)
        if schema is None and schema_i is not None and schema_i < len(node.args):
            schema = _resolve_str(node.args[schema_i], facts.constants)
        if func_name == "to_sql" and table is None and node.args:
            table = _resolve_str(node.args[0], facts.constants)
    if table:
        facts.write_tables.append(TableRef(schema=schema, name=table))


def _sql_from_text(text: str | None, facts: ModuleFacts) -> None:
    if not text:
        return
    if _SQL_DML.search(text):
        facts.has_write = True
    for match in _SQL_INTO.finditer(text):
        facts.has_write = True
        facts.write_tables.append(TableRef(schema=match.group(1), name=match.group(2)))


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


def _resolve_str(node: ast.AST | None, constants: dict[str, str]) -> str | None:
    if node is None:
        return None
    direct = _const_str(node)
    if direct is not None:
        return direct
    if isinstance(node, ast.Name):
        return constants.get(node.id)
    if isinstance(node, ast.JoinedStr):
        return _joined_str(node, constants)
    return None


def _is_dag_module(tree: ast.AST) -> bool:
    for node in ast.walk(tree):
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
    for node in ast.walk(tree):
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
