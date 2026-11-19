"""Bounded symbolic analysis used only by the registry Python lineage adapter.

Values are syntax-derived facts, never objects imported from loader sources.
Unknown runtime data cannot supply table identity. Local wrappers are followed
by signature rather than by assumptions about their names or argument order.
"""

from __future__ import annotations

import ast
import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from domains.catalog.lineage_adapters.airflow_syntax import (
    TableRef,
)

UNKNOWN = object()
_BLOCKED_IMPORT = object()
_UNKNOWN_TEXT = "__PORTAL_UNKNOWN_VALUE__"
MAX_MODULES = 80
MAX_FILE_BYTES = 2_000_000
MAX_NODES = 40_000
MAX_STEPS = 30_000
MAX_DEPTH = 24
MAX_CALLS = 512
MAX_ITERATIONS = 1024
MAX_ITEMS = 128
_IDENT = r'(?:"[A-Za-z_][\w]*"|[A-Za-z_][\w]*)'
_SQL = re.compile(
    rf"\b(?:INSERT\s+INTO|UPDATE|MERGE\s+INTO|COPY)\s+" rf"({_IDENT})(?:\s*\.\s*({_IDENT}))?",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class _Symbol:
    path: Path
    name: str = ""
    owner: str = ""
    absolute: str = ""


@dataclass(frozen=True)
class _Bound:
    function: _Symbol
    receiver: _Symbol


@dataclass(frozen=True)
class _External:
    name: str


@dataclass(frozen=True)
class _Namespace:
    name: str
    source: Path


@dataclass(frozen=True)
class _Super:
    owner: _Symbol
    receiver: _Symbol


@dataclass(frozen=True)
class _Dml:
    model: Any


@dataclass
class _Module:
    tree: ast.Module
    symbols: dict[str, ast.AST] = field(default_factory=dict)
    imports: dict[str, Any] = field(default_factory=dict)
    dependencies: set[Path] = field(default_factory=set)


@dataclass
class LoaderAnalysis:
    """Confirmed write identities, source evidence and non-fatal diagnostics."""

    refs: list[TableRef] = field(default_factory=list)
    evidence: list[dict] = field(default_factory=list)
    diagnostics: list[dict] = field(default_factory=list)
    source_files: list[str] = field(default_factory=list)


class _Limit(Exception):
    pass


class AmbiguousModule(Exception):
    """Multiple confined source files claim the same absolute module name."""


class PythonModuleRoots:
    """Normalize Python-only roots and resolve sources without search-order wins."""

    def __init__(self, roots: Path | Iterable[Path]):
        self.roots: list[Path] = []
        self.invalid: list[str] = []
        seen: set[Path] = set()
        for index, raw in enumerate([roots] if isinstance(roots, Path) else roots, 1):
            try:
                root = raw.resolve()
                if root in seen:
                    continue
                seen.add(root)
                if not root.is_dir():
                    self.invalid.append(f"root_{index}")
                    continue
                self.roots.append(root)
            except (OSError, ValueError, RuntimeError):
                self.invalid.append(f"root_{index}")

    @classmethod
    def from_setting(cls, value: str | None) -> PythonModuleRoots:
        """Split the existing string setting; empty components are not roots."""
        return cls(Path(part.strip()) for part in (value or "").split(";") if part.strip())

    def owner(self, path: Path) -> Path | None:
        """Use the most specific configured root for overlapping source trees."""
        resolved = path.resolve()
        owners = [root for root in self.roots if resolved.is_relative_to(root)]
        return max(owners, key=lambda root: len(root.parts)) if owners else None

    def label(self, path: Path) -> str:
        """Return portable provenance, never a host-specific absolute path."""
        root = self.owner(path)
        if root is None:
            return "<outside_python_roots>"
        relative = path.resolve().relative_to(root).as_posix()
        return relative if len(self.roots) == 1 else f"root_{self.roots.index(root) + 1}/{relative}"

    def _candidate(self, base: Path, root: Path) -> Path | None:
        try:
            for path in (base.with_suffix(".py"), base / "__init__.py"):
                if path.is_file() and path.resolve().is_relative_to(root):
                    return path.resolve()
        except (OSError, ValueError, RuntimeError):
            return None
        return None

    def namespace(self, spec: str) -> bool:
        """Recognize confined namespace directories without executing packages."""
        return any(
            (base := root.joinpath(*spec.split("."))).is_dir()
            and base.resolve().is_relative_to(root)
            for root in self.roots
        )

    def resolve(self, spec: str, from_file: Path | None = None, level: int = 0) -> Path | None:
        """Anchor relative imports; reject collisions in absolute module prefixes."""
        parts = spec.split(".") if spec else []
        if any(not part.isidentifier() for part in parts):
            return None
        if level:
            root = self.owner(from_file) if from_file is not None else None
            if root is None:
                return None
            base = from_file.resolve().parent
            for _ in range(level - 1):
                base = base.parent
            if not base.is_relative_to(root):
                return None
            return self._candidate(base.joinpath(*parts), root)
        if not parts:
            return None
        # A unique child must not silently combine two identically named packages.
        for length in range(1, len(parts) + 1):
            hits = {
                candidate
                for root in self.roots
                if (candidate := self._candidate(root.joinpath(*parts[:length]), root)) is not None
            }
            if len(hits) > 1:
                raise AmbiguousModule(spec)
            if length == len(parts):
                return next(iter(hits), None)
        return None


class PythonLoaderAnalyzer:
    """Resolve one registry entry point within a confined, finite source graph."""

    def __init__(self, root: Path | Iterable[Path] | PythonModuleRoots):
        self.sources = root if isinstance(root, PythonModuleRoots) else PythonModuleRoots(root)
        self.result = LoaderAnalysis()
        self.modules: dict[Path, _Module | None] = {}
        self.resolving: set[tuple] = set()
        self.stack: list[_Symbol] = []
        self.steps = 0
        self.calls = 0
        self.iterations = 0
        self.pure = 0

    def analyze(self, entry: Path, entry_point: str | None = None) -> LoaderAnalysis:
        """Analyze selected code without importing or executing source modules."""
        try:
            module = self._module(entry)
            if module is None:
                return self.result
            selected: Any = UNKNOWN
            if entry_point:
                selected = _Symbol(entry.resolve())
                for part in entry_point.split("."):
                    selected = self._attr(selected, part)
            else:
                classes = [
                    _Symbol(entry.resolve(), name)
                    for name, node in module.symbols.items()
                    if isinstance(node, ast.ClassDef)
                    and isinstance(
                        self._attr(_Symbol(entry.resolve(), name), "load_file"), (_Symbol, _Bound)
                    )
                ]
                candidates = classes or [
                    _Symbol(entry.resolve(), name)
                    for name, node in module.symbols.items()
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                ]
                if len(candidates) == 1:
                    selected = candidates[0]
                else:
                    self._diagnostic("ENTRY_POINT_AMBIGUOUS", entry)
                    return self.result
            if isinstance(selected, _Symbol) and isinstance(self._node(selected), ast.ClassDef):
                selected = self._attr(selected, "load_file")
            if not isinstance(selected, (_Symbol, _Bound)) or not isinstance(
                self._node(selected.function if isinstance(selected, _Bound) else selected),
                (ast.FunctionDef, ast.AsyncFunctionDef),
            ):
                self._diagnostic("ENTRY_POINT_MISSING", entry)
                return self.result
            self._invoke(selected, [], {})
        except (_Limit, RecursionError):
            self._diagnostic("ANALYSIS_LIMIT", entry)
        self.result.source_files = sorted(
            self.sources.label(path) for path, module in self.modules.items() if module is not None
        )
        return self.result

    def _tick(self):
        self.steps += 1
        if self.steps > MAX_STEPS:
            raise _Limit()

    def _diagnostic(self, code, path, node=None):
        payload = {
            "code": code,
            "message": code.replace("_", " ").lower(),
            "file": self.sources.label(path),
            "line": getattr(node, "lineno", 1),
        }
        if payload not in self.result.diagnostics:
            self.result.diagnostics.append(payload)

    def _module(self, path):
        path = path.resolve()
        if self.sources.owner(path) is None:
            return None
        if path in self.modules:
            return self.modules[path]
        if len(self.modules) >= MAX_MODULES:
            raise _Limit()
        self.modules[path] = None
        try:
            if path.stat().st_size > MAX_FILE_BYTES:
                self._diagnostic("SOURCE_LIMIT", path)
                return None
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (OSError, UnicodeError, SyntaxError, ValueError):
            self._diagnostic("MODULE_UNAVAILABLE", path)
            return None
        if sum(1 for _ in ast.walk(tree)) > MAX_NODES:
            self._diagnostic("SOURCE_LIMIT", path)
            return None
        module = _Module(tree)
        self.modules[path] = module
        self.result.source_files.append(self.sources.label(path))
        for node in tree.body:
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                module.symbols[node.name] = node
            elif isinstance(node, (ast.Assign, ast.AnnAssign)):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                for target in targets:
                    for name in ast.walk(target):
                        if isinstance(name, ast.Name):
                            module.symbols[name.id] = node
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    spec = alias.name if alias.asname else alias.name.split(".")[0]
                    full = self._resolve_import(alias.name, path, node)
                    dep = (
                        self._resolve_import(spec, path, node)
                        if full is not _BLOCKED_IMPORT
                        else _BLOCKED_IMPORT
                    )
                    if isinstance(full, Path):
                        module.dependencies.add(full)
                    module.imports[alias.asname or spec] = (
                        _BLOCKED_IMPORT
                        if dep is _BLOCKED_IMPORT
                        else (
                            _Symbol(dep, absolute=spec)
                            if dep
                            else (
                                _Namespace(spec, path)
                                if isinstance(full, Path) or self.sources.namespace(spec)
                                else _External(spec)
                            )
                        )
                    )
            elif isinstance(node, ast.ImportFrom):
                dep = self._resolve_import(node.module or "", path, node, node.level)
                if isinstance(dep, Path):
                    module.dependencies.add(dep)
                for alias in node.names:
                    if alias.name == "*":
                        self._diagnostic("IMPORT_UNRESOLVED", path, node)
                        continue
                    nested = self._resolve_import(
                        ".".join(filter(None, [node.module, alias.name])), path, node, node.level
                    )
                    if isinstance(nested, Path) and dep is not _BLOCKED_IMPORT:
                        module.dependencies.add(nested)
                    module.imports[alias.asname or alias.name] = (
                        _BLOCKED_IMPORT
                        if dep is _BLOCKED_IMPORT or nested is _BLOCKED_IMPORT
                        else (
                            _Symbol(
                                nested,
                                absolute=(
                                    ".".join(filter(None, [node.module, alias.name]))
                                    if not node.level
                                    else ""
                                ),
                            )
                            if nested
                            else (
                                _Symbol(dep, alias.name)
                                if dep
                                else _External(f"{node.module}.{alias.name}")
                            )
                        )
                    )
        return module

    def _resolve_import(self, spec, path, node, level=0):
        try:
            return self.sources.resolve(spec, path, level)
        except AmbiguousModule:
            self._diagnostic("MODULE_AMBIGUOUS", path, node)
            return _BLOCKED_IMPORT

    def _node(self, symbol):
        module = self._module(symbol.path)
        if module is None:
            return None
        node = module.symbols.get(symbol.owner or symbol.name)
        if symbol.owner and isinstance(node, ast.ClassDef):
            return next(
                (item for item in node.body if getattr(item, "name", None) == symbol.name),
                None,
            )
        return node

    def _value(self, symbol):
        self._tick()
        key = (symbol.path, symbol.owner, symbol.name)
        if key in self.resolving or len(self.resolving) >= MAX_DEPTH:
            self._diagnostic("RESOLUTION_CYCLE", symbol.path)
            return UNKNOWN
        module = self._module(symbol.path)
        if module is None:
            return UNKNOWN
        if not symbol.name:
            return symbol
        imported = module.imports.get(symbol.name) if not symbol.owner else None
        if imported is not None:
            self.resolving.add(key)
            try:
                return self._value(imported) if isinstance(imported, _Symbol) else imported
            finally:
                self.resolving.remove(key)
        node = self._node(symbol)
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            return symbol
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            self.resolving.add(key)
            self.pure += 1
            try:
                value = self._expr(node.value, {}, symbol.path)
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                env = {}
                for target in targets:
                    self._assign(target, value, env, symbol.path)
                return env.get(symbol.name, UNKNOWN)
            finally:
                self.pure -= 1
                self.resolving.remove(key)
        return UNKNOWN

    def _attr(self, value, name, seen=None):
        self._tick()
        if value is _BLOCKED_IMPORT:
            return _BLOCKED_IMPORT
        if isinstance(value, _Namespace):
            spec = f"{value.name}.{name}"
            try:
                dep = self.sources.resolve(spec)
            except AmbiguousModule:
                self._diagnostic("MODULE_AMBIGUOUS", value.source)
                return _BLOCKED_IMPORT
            return (
                _Symbol(dep, absolute=spec)
                if dep
                else (_Namespace(spec, value.source) if self.sources.namespace(spec) else UNKNOWN)
            )
        if isinstance(value, _External):
            return _External(f"{value.name}.{name}")
        if isinstance(value, _Super):
            node = self._node(value.owner)
            if isinstance(node, ast.ClassDef):
                for base in node.bases:
                    parent = self._expr(base, {}, value.owner.path)
                    found = self._attr(parent, name)
                    if isinstance(found, _Bound):
                        return _Bound(found.function, value.receiver)
                    if found is not UNKNOWN and not isinstance(found, _External):
                        return found
            return UNKNOWN
        if not isinstance(value, _Symbol):
            return UNKNOWN
        if not value.name:
            found = self._value(_Symbol(value.path, name))
            if found is UNKNOWN:
                module = self._module(value.path)
                parent = value.path.parent if value.path.name == "__init__.py" else None
                if module and parent:
                    if value.absolute:
                        spec = f"{value.absolute}.{name}"
                        try:
                            nested = self.sources.resolve(spec)
                        except AmbiguousModule:
                            self._diagnostic("MODULE_AMBIGUOUS", value.path)
                            return _BLOCKED_IMPORT
                        return _Symbol(nested, absolute=spec) if nested else UNKNOWN
                    nested = parent / f"{name}.py"
                    package = parent / name / "__init__.py"
                    for path in (nested, package):
                        if path.is_file() and path.resolve().is_relative_to(
                            self.sources.owner(value.path)
                        ):
                            return _Symbol(path.resolve())
            return found
        node = self._node(value)
        if not isinstance(node, ast.ClassDef):
            return UNKNOWN
        seen = set() if seen is None else seen
        if value in seen or len(seen) >= MAX_DEPTH:
            self._diagnostic("RESOLUTION_CYCLE", value.path, node)
            return UNKNOWN
        seen.add(value)
        class_env = {}
        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                function = _Symbol(value.path, item.name, value.name)
                if any(
                    isinstance(d, ast.Name) and d.id == "staticmethod" for d in item.decorator_list
                ):
                    class_env[item.name] = function
                else:
                    class_env[item.name] = _Bound(function, value)
            if isinstance(item, (ast.Assign, ast.AnnAssign)):
                targets = item.targets if isinstance(item, ast.Assign) else [item.target]
                self.pure += 1
                try:
                    resolved = self._expr(item.value, class_env, value.path)
                finally:
                    self.pure -= 1
                for target in targets:
                    self._assign(target, resolved, class_env, value.path)
        if name in class_env:
            return class_env[name]
        for base in node.bases:
            parent = self._expr(base, {}, value.path)
            found = self._attr(parent, name, seen)
            if isinstance(found, _Bound):
                return _Bound(found.function, value)
            if found is not UNKNOWN and not isinstance(found, _External):
                return found
        return UNKNOWN

    def _expr(self, node, env, path):
        self._tick()
        if isinstance(node, ast.Constant):
            return node.value if isinstance(node.value, (str, int, bool, type(None))) else UNKNOWN
        if isinstance(node, ast.Name):
            return env[node.id] if node.id in env else self._value(_Symbol(path, node.id))
        if isinstance(node, ast.Attribute):
            return self._attr(self._expr(node.value, env, path), node.attr)
        if isinstance(node, (ast.Tuple, ast.List)):
            if len(node.elts) > MAX_ITEMS:
                raise _Limit()
            values = []
            for item in node.elts:
                value = self._expr(item.value if isinstance(item, ast.Starred) else item, env, path)
                if isinstance(item, ast.Starred):
                    if not isinstance(value, (tuple, list)):
                        return UNKNOWN
                    values.extend(value)
                else:
                    values.append(value)
            return tuple(values)
        if isinstance(node, ast.Dict):
            if len(node.keys) > MAX_ITEMS:
                raise _Limit()
            result = {}
            for key, value in zip(node.keys, node.values):
                k = self._expr(key, env, path)
                v = self._expr(value, env, path)
                if not isinstance(k, (str, int, tuple)):
                    return UNKNOWN
                result[k] = v
            return result
        if isinstance(node, ast.Subscript):
            value = self._expr(node.value, env, path)
            key = self._expr(node.slice, env, path)
            try:
                return value[key] if isinstance(value, (dict, tuple, str)) else UNKNOWN
            except (KeyError, IndexError, TypeError):
                return UNKNOWN
        if isinstance(node, ast.JoinedStr):
            parts = []
            for item in node.values:
                value = self._expr(
                    item.value if isinstance(item, ast.FormattedValue) else item, env, path
                )
                # Unknown SQL payload does not erase a proven target. The marker
                # itself is forbidden in target identity by _write.
                parts.append(str(value) if isinstance(value, (str, int)) else _UNKNOWN_TEXT)
            return "".join(parts)
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            left, right = self._expr(node.left, env, path), self._expr(node.right, env, path)
            if isinstance(left, str) and isinstance(right, str):
                return left + right
        if isinstance(node, ast.Call):
            return self._call(node, env, path)
        # Traverse nested expressions for calls, but never turn unknown data into identity.
        for child in ast.iter_child_nodes(node) if node is not None else ():
            self._expr(child, env, path)
        return UNKNOWN

    def _call(self, node, env, path):
        args = []
        for item in node.args:
            value = self._expr(item.value if isinstance(item, ast.Starred) else item, env, path)
            if isinstance(item, ast.Starred):
                if not isinstance(value, tuple):
                    self._diagnostic("CALL_ARGUMENTS_UNKNOWN", path, node)
                    return UNKNOWN
                args.extend(value)
            else:
                args.append(value)
        kwargs = {}
        for item in node.keywords:
            value = self._expr(item.value, env, path)
            if item.arg:
                kwargs[item.arg] = value
            elif isinstance(value, dict) and all(isinstance(key, str) for key in value):
                kwargs.update(value)
            else:
                self._diagnostic("CALL_ARGUMENTS_UNKNOWN", path, node)
                return UNKNOWN
        name = (
            node.func.attr if isinstance(node.func, ast.Attribute) else getattr(node.func, "id", "")
        )
        owner = (
            self._expr(node.func.value, env, path)
            if isinstance(node.func, ast.Attribute)
            else UNKNOWN
        )
        if isinstance(node.func, ast.Name) and name == "super" and self.stack:
            receiver = env.get("cls", env.get("self", UNKNOWN))
            function = self.stack[-1]
            if isinstance(receiver, _Symbol) and function.owner:
                return _Super(_Symbol(function.path, function.owner), receiver)
        if isinstance(owner, dict) and name in {"get", "items", "keys", "values"}:
            if name == "get":
                try:
                    return (
                        owner.get(args[0], args[1] if len(args) > 1 else None) if args else UNKNOWN
                    )
                except TypeError:
                    return UNKNOWN
            return tuple(getattr(owner, name)())
        function = (
            self._attr(owner, name)
            if isinstance(node.func, ast.Attribute)
            else self._expr(node.func, env, path)
        )
        # Unknown runtime receivers may still be dataframes; an explicitly
        # blocked local import must never fall through to name-based writers.
        if owner is _BLOCKED_IMPORT or function is _BLOCKED_IMPORT:
            return _BLOCKED_IMPORT
        if isinstance(function, (_Symbol, _Bound)):
            symbol = function.function if isinstance(function, _Bound) else function
            if isinstance(self._node(symbol), ast.ClassDef):
                return symbol
            return self._invoke(function, args, kwargs) if not self.pure else UNKNOWN
        if self.pure:
            return UNKNOWN
        if name == "to_sql":
            table = kwargs.get("name", args[0] if args else UNKNOWN)
            schema = kwargs.get("schema", args[2] if len(args) > 2 else None)
            self._write(schema, table, path, node, "to_sql")
        elif isinstance(function, _External) and function.name in {
            "sqlalchemy.insert",
            "sqlalchemy.dialects.postgresql.insert",
        }:
            return _Dml(args[0] if args else UNKNOWN)
        elif isinstance(owner, _Dml) and name in {
            "values",
            "returning",
            "on_conflict_do_update",
            "on_conflict_do_nothing",
        }:
            return owner
        elif (
            name in {"add", "add_all", "bulk_insert_mappings", "bulk_save_objects"}
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id in {"session", "sess", "db_session"}
        ):
            values = args[0] if args else UNKNOWN
            for value in values if isinstance(values, tuple) else (values,):
                self._orm(value, path, node)
        elif name in {"execute", "executemany", "exec_driver_sql"}:
            sql = args[0] if args else kwargs.get("statement", UNKNOWN)
            if isinstance(sql, _Dml):
                self._orm(sql.model, path, node)
            elif isinstance(sql, str):
                for match in _SQL.finditer(sql):
                    first, second = match.groups()
                    self._write(
                        first.strip('"') if second else None,
                        (second or first).strip('"'),
                        path,
                        node,
                        "sql",
                    )
            elif sql is UNKNOWN:
                self._diagnostic("WRITE_TARGET_UNKNOWN", path, node)
        if isinstance(function, _External) and function.name in {
            "sqlalchemy.text",
            "sqlalchemy.sql.text",
        }:
            return args[0] if args else UNKNOWN
        return UNKNOWN

    def _orm(self, value, path, node):
        table = self._attr(value, "__tablename__")
        options = self._attr(value, "__table_args__")
        if isinstance(options, tuple):
            options = next((item for item in options if isinstance(item, dict)), UNKNOWN)
        schema = (
            options.get("schema")
            if isinstance(options, dict)
            else UNKNOWN if self._declares(value, "__table_args__") else None
        )
        self._write(schema, table, path, node, "orm")

    def _declares(self, value, name, seen=None):
        """Distinguish absent ORM options from an explicitly unknown schema."""
        self._tick()
        if not isinstance(value, _Symbol):
            return False
        seen = set() if seen is None else seen
        if value in seen or len(seen) >= MAX_DEPTH:
            return False
        seen.add(value)
        node = self._node(value)
        if not isinstance(node, ast.ClassDef):
            return False
        for statement in node.body:
            if isinstance(statement, (ast.Assign, ast.AnnAssign)):
                targets = (
                    statement.targets if isinstance(statement, ast.Assign) else [statement.target]
                )
                if any(
                    isinstance(item, ast.Name) and item.id == name
                    for target in targets
                    for item in ast.walk(target)
                ):
                    return True
        return any(
            self._declares(self._expr(base, {}, value.path), name, seen) for base in node.bases
        )

    def _write(self, schema, table, path, node, pattern):
        if (
            not isinstance(table, str)
            or not table
            or _UNKNOWN_TEXT in table
            or (schema is not None and (not isinstance(schema, str) or _UNKNOWN_TEXT in schema))
        ):
            self._diagnostic("WRITE_TARGET_UNKNOWN", path, node)
            return
        ref = TableRef(schema, table, str(path))
        if not any((r.schema, r.name) == (schema, table) for r in self.result.refs):
            self.result.refs.append(ref)
        evidence = {
            "schema": schema,
            "table": table,
            "file": self.sources.label(path),
            "line": node.lineno,
            "pattern": pattern,
        }
        if evidence not in self.result.evidence:
            self.result.evidence.append(evidence)

    def _invoke(self, function, args, kwargs):
        symbol = function.function if isinstance(function, _Bound) else function
        node = self._node(symbol)
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return UNKNOWN
        if symbol in self.stack:
            self._diagnostic("CALL_CYCLE", symbol.path, node)
            return UNKNOWN
        self.calls += 1
        if self.calls > MAX_CALLS or len(self.stack) >= MAX_DEPTH:
            raise _Limit()
        params = node.args.posonlyargs + node.args.args
        values = ([function.receiver] if isinstance(function, _Bound) else []) + args
        env = {param.arg: UNKNOWN for param in params + node.args.kwonlyargs}
        for param, default in zip(params[-len(node.args.defaults) :], node.args.defaults):
            env[param.arg] = self._expr(default, {}, symbol.path)
        for param, default in zip(node.args.kwonlyargs, node.args.kw_defaults):
            if default is not None:
                env[param.arg] = self._expr(default, {}, symbol.path)
        env.update({param.arg: value for param, value in zip(params, values)})
        env.update({name: value for name, value in kwargs.items() if name in env})
        self.stack.append(symbol)
        try:
            returned, value = self._block(node.body, env, symbol.path)
            return value if returned else UNKNOWN
        finally:
            self.stack.pop()

    def _assign(self, target, value, env, path):
        if isinstance(target, ast.Name):
            env[target.id] = value
        elif isinstance(target, (ast.Tuple, ast.List)):
            values = value if isinstance(value, (tuple, list)) else ()
            for index, item in enumerate(target.elts):
                self._assign(item, values[index] if index < len(values) else UNKNOWN, env, path)
        elif isinstance(target, ast.Subscript):
            owner = self._expr(target.value, env, path)
            key = self._expr(target.slice, env, path)
            if isinstance(owner, dict) and isinstance(key, (str, int)):
                if len(owner) >= MAX_ITEMS:
                    raise _Limit()
                owner[key] = value

    def _block(self, statements, env, path):
        for node in statements:
            self._tick()
            if isinstance(node, (ast.Assign, ast.AnnAssign)):
                value = self._expr(node.value, env, path)
                for target in node.targets if isinstance(node, ast.Assign) else [node.target]:
                    self._assign(target, value, env, path)
            elif isinstance(node, ast.Expr):
                if not isinstance(node.value, ast.Constant):
                    self._expr(node.value, env, path)
            elif isinstance(node, ast.Return):
                return True, self._expr(node.value, env, path)
            elif isinstance(node, (ast.For, ast.AsyncFor)):
                values = self._expr(node.iter, env, path)
                if isinstance(values, dict):
                    values = tuple(values)
                if not isinstance(values, (tuple, list)):
                    values = (UNKNOWN,)
                if len(values) > MAX_ITEMS:
                    raise _Limit()
                for value in values:
                    self.iterations += 1
                    if self.iterations > MAX_ITERATIONS:
                        raise _Limit()
                    self._assign(node.target, value, env, path)
                    self._block(node.body, env, path)
                self._block(node.orelse, env, path)
            elif isinstance(node, ast.If):
                test_node = node.test
                if (
                    isinstance(test_node, ast.Compare)
                    and len(test_node.ops) == 1
                    and isinstance(test_node.ops[0], ast.Eq)
                    and any(
                        isinstance(item, ast.Name) and item.id == "__name__"
                        for item in ast.walk(test_node)
                    )
                    and any(
                        isinstance(item, ast.Constant) and item.value == "__main__"
                        for item in ast.walk(test_node)
                    )
                ):
                    continue
                test = self._expr(node.test, env, path)
                if isinstance(test, (bool, int)):
                    returned, value = self._block(node.body if test else node.orelse, env, path)
                    if returned:
                        return returned, value
                else:
                    branches = []
                    for branch in (node.body, node.orelse):
                        branch_env = {
                            k: dict(v) if isinstance(v, dict) else v for k, v in env.items()
                        }
                        self._block(branch, branch_env, path)
                        branches.append(branch_env)
                    for key in branches[0].keys() | branches[1].keys():
                        a, b = (branch.get(key, UNKNOWN) for branch in branches)
                        env[key] = a if a == b else UNKNOWN
            elif isinstance(node, (ast.With, ast.AsyncWith)):
                for item in node.items:
                    self._expr(item.context_expr, env, path)
                returned, value = self._block(node.body, env, path)
                if returned:
                    return returned, value
            elif isinstance(node, ast.Try):
                self._block(node.body, env, path)
                for handler in node.handlers:
                    self._block(handler.body, dict(env), path)
                self._block(node.orelse, env, path)
                self._block(node.finalbody, env, path)
            elif isinstance(node, ast.While):
                self._diagnostic("DYNAMIC_LOOP", path, node)
                self._block(node.body, dict(env), path)
        return False, UNKNOWN
