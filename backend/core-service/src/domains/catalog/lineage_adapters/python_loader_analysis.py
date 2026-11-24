"""Bounded symbolic analysis used only by the registry Python lineage adapter.

Values are syntax-derived facts, never objects imported from loader sources.
Unknown runtime data cannot supply table identity. Local wrappers are followed
by signature rather than by assumptions about their names or argument order.
"""

from __future__ import annotations

import ast
import re
import string
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from domains.catalog.lineage_adapters.airflow_syntax import (
    TableRef,
)
from domains.catalog.lineage_adapters.python_sql_writes import sql_write_targets

UNKNOWN = object()
_BLOCKED_IMPORT = object()
_OPAQUE = object()
_BREAK = object()
_CONTINUE = object()
_UNKNOWN_TEXT = "__PORTAL_UNKNOWN_VALUE__"
MAX_MODULES = 80
MAX_FILE_BYTES = 2_000_000
MAX_NODES = 40_000
MAX_STEPS = 30_000
MAX_DEPTH = 24
MAX_CALLS = 512
MAX_ITERATIONS = 1024
MAX_ITEMS = 128
MAX_TEXT = 262144
_MISSING = object()


@dataclass(frozen=True)
class _Symbol:
    path: Path
    name: str = ""
    owner: str = ""
    absolute: str = ""
    definition: int = 0


@dataclass(frozen=True)
class _Imported(_Symbol):
    """A from-import, resolved as a package attribute before submodule fallback."""


@dataclass(frozen=True)
class _Bound:
    function: _Symbol
    receiver: Any


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
    receiver: Any


@dataclass(frozen=True)
class _Dml:
    model: Any


@dataclass(frozen=True)
class _OrmTable:
    model: _Symbol


@dataclass(frozen=True)
class _Constraint:
    pass


@dataclass(frozen=True)
class _Metadata:
    schema: Any


@dataclass(frozen=True)
class _Table:
    schema: Any
    name: Any


@dataclass(frozen=True)
class _Base:
    metadata: _Metadata


@dataclass(frozen=True)
class _Receiver:
    kind: str


@dataclass(frozen=True)
class _SqlText:
    text: str


@dataclass(frozen=True)
class _ReadStatement:
    pass


@dataclass(frozen=True)
class _OrmQuery:
    model: Any


@dataclass(frozen=True)
class _SqlFragment:
    text: str


@dataclass
class _Instance:
    model: _Symbol
    attrs: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class _EnumMember:
    name: str
    value: Any


@dataclass(frozen=True)
class _Field:
    default: Any = _MISSING
    factory: Any = _MISSING
    init: Any = True
    kw_only: Any = _MISSING


@dataclass(frozen=True)
class _Method:
    receiver: Any
    name: str


@dataclass
class _Module:
    tree: ast.Module
    symbols: dict[str, ast.AST] = field(default_factory=dict)
    imports: dict[str, Any] = field(default_factory=dict)
    dependencies: set[Path] = field(default_factory=set)
    bindings: dict[str, list[tuple[int, Any]]] = field(default_factory=dict)


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
        try:
            resolved = path.resolve()
        except (OSError, ValueError, RuntimeError):
            return None
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
        # A regular package owns its children. Namespace packages may span
        # roots, but a child from a different tree cannot complete a regular one.
        package_dir = None
        for length in range(1, len(parts) + 1):
            hits = {
                candidate
                for root in self.roots
                if (candidate := self._candidate(root.joinpath(*parts[:length]), root)) is not None
            }
            if len(hits) > 1:
                raise AmbiguousModule(spec)
            hit = next(iter(hits), None)
            if hit is not None and package_dir is not None and not hit.is_relative_to(package_dir):
                raise AmbiguousModule(spec)
            if length == len(parts):
                return hit
            if hit is not None:
                if hit.name != "__init__.py":
                    return None
                package_dir = hit.parent
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
        self.cutoffs: dict[Path, int] = {}
        self.mro_cache: dict[_Symbol, list] = {}
        self.generated_configs: dict[_Symbol, Any] = {}
        self.invalidated_members: set[tuple[_Symbol, str]] = set()
        self.invalidated_globals: set[tuple[Path, str]] = set()
        self.mutable_origins: dict[int, tuple[Any, set[tuple]]] = {}

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
                    _Symbol(entry.resolve(), name, definition=node.lineno)
                    for name, node in module.symbols.items()
                    if isinstance(node, ast.ClassDef)
                    and isinstance(
                        self._attr(_Symbol(entry.resolve(), name, definition=node.lineno), "load_file"), (_Symbol, _Bound)
                    )
                ]
                candidates = classes or [
                    _Symbol(entry.resolve(), name, definition=node.lineno)
                    for name, node in module.symbols.items()
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                ]
                if len(candidates) == 1:
                    selected = candidates[0]
                else:
                    self._diagnostic("ENTRY_POINT_AMBIGUOUS", entry)
                    return self.result
            if isinstance(selected, _Symbol) and isinstance(self._node(selected), ast.ClassDef):
                selected = self._entry_method(selected)
            if not isinstance(selected, (_Symbol, _Bound)) or not isinstance(
                self._node(selected.function if isinstance(selected, _Bound) else selected),
                (ast.FunctionDef, ast.AsyncFunctionDef),
            ):
                self._diagnostic("ENTRY_POINT_MISSING", entry)
                return self.result
            self._invoke(selected, [], {}, entry=True)
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
        for node in self._module_statements(tree.body):
            bindings = {}
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                bindings[node.name] = node
            elif isinstance(node, (ast.Assign, ast.AnnAssign)):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                for target in targets:
                    for name in self._target_names(target):
                        bindings[name] = node
                    if isinstance(target, (ast.Attribute, ast.Subscript)):
                        # Do not reuse a stale constant after an unsupported mutation.
                        root = target.value
                        while isinstance(root, (ast.Attribute, ast.Subscript)):
                            root = root.value
                        if isinstance(root, ast.Name):
                            bindings[root.id] = UNKNOWN
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                bindings = self._imports_for(node, path, module)
            elif isinstance(node, (ast.If, ast.Try, ast.For, ast.While, ast.With, ast.AugAssign, ast.Delete, ast.Match)):
                # Conditional or unsupported module-level definitions cannot be assumed to run.
                for child in ast.walk(node):
                    if isinstance(child, ast.Name) and isinstance(child.ctx, (ast.Store, ast.Del)):
                        bindings[child.id] = UNKNOWN
                    elif isinstance(child, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                        bindings[child.name] = UNKNOWN
                    elif isinstance(child, (ast.Import, ast.ImportFrom)):
                        for alias in child.names:
                            if alias.name != "*":
                                bindings[alias.asname or alias.name.split(".")[0]] = UNKNOWN
            for name, binding in bindings.items():
                module.bindings.setdefault(name, []).append((node.lineno, binding))
                if isinstance(binding, ast.AST):
                    module.symbols[name] = binding
                    module.imports.pop(name, None)
                else:
                    module.symbols.pop(name, None)
                    module.imports[name] = binding
        return module

    @staticmethod
    def _module_statements(statements):
        for node in statements:
            if isinstance(node, ast.If):
                test = node.test
                if isinstance(test, ast.Constant) and type(test.value) in (bool, int, str, type(None)):
                    yield from PythonLoaderAnalyzer._module_statements(node.body if test.value else node.orelse)
                    continue
                if isinstance(test, ast.Compare) and len(test.ops) == 1 and isinstance(test.ops[0], (ast.Eq, ast.NotEq)):
                    pair = (test.left, test.comparators[0])
                    if any(isinstance(x, ast.Name) and x.id == "__name__" for x in pair) and any(isinstance(x, ast.Constant) and x.value == "__main__" for x in pair):
                        yield from PythonLoaderAnalyzer._module_statements(node.orelse if isinstance(test.ops[0], ast.Eq) else node.body)
                        continue
            yield node

    @staticmethod
    def _target_names(target):
        if isinstance(target, ast.Name):
            yield target.id
        elif isinstance(target, (ast.Tuple, ast.List)):
            for child in target.elts:
                yield from PythonLoaderAnalyzer._target_names(child)
        elif isinstance(target, ast.Starred):
            yield from PythonLoaderAnalyzer._target_names(target.value)

    def _imports_for(self, node, path, module):
        bindings = {}
        if isinstance(node, ast.Import):
            for alias in node.names:
                spec = alias.name if alias.asname else alias.name.split(".")[0]
                full = self._resolve_import(alias.name, path, node)
                dep = self._resolve_import(spec, path, node) if full is not _BLOCKED_IMPORT else full
                if isinstance(full, Path):
                    module.dependencies.add(full)
                bindings[alias.asname or spec] = (
                    _BLOCKED_IMPORT if dep is _BLOCKED_IMPORT else
                    _Symbol(dep, absolute=spec) if dep else
                    _Namespace(spec, path) if isinstance(full, Path) or self.sources.namespace(spec)
                    else _External(spec)
                )
        else:
            dep = self._resolve_import(node.module or "", path, node, node.level)
            if isinstance(dep, Path):
                module.dependencies.add(dep)
            for alias in node.names:
                if alias.name == "*":
                    self._diagnostic("IMPORT_UNRESOLVED", path, node)
                    continue
                spec = ".".join(filter(None, [node.module, alias.name]))
                nested = self._resolve_import(spec, path, node, node.level)
                if isinstance(nested, Path) and dep is not _BLOCKED_IMPORT:
                    module.dependencies.add(nested)
                if dep is _BLOCKED_IMPORT or nested is _BLOCKED_IMPORT:
                    value = _BLOCKED_IMPORT
                elif isinstance(dep, Path):
                    # A package's explicit exported attribute wins over a sibling module.
                    value = _Imported(dep, alias.name, absolute=(node.module or "") if not node.level else "")
                elif isinstance(nested, Path):
                    value = _Symbol(nested, absolute=spec if not node.level else "")
                elif node.level:
                    value = _BLOCKED_IMPORT
                    self._diagnostic("IMPORT_UNRESOLVED", path, node)
                else:
                    value = _External(spec)
                bindings[alias.asname or alias.name] = value
        return bindings

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
        parts = (symbol.owner or symbol.name).split(".")
        if not parts[0]:
            return None
        if symbol.definition:
            node = next((binding for line, binding in module.bindings.get(parts[0], ())
                         if line == symbol.definition and isinstance(binding, ast.AST)), None)
        else:
            node = module.symbols.get(parts[0])
        for part in parts[1:] + ([symbol.name] if symbol.owner else []):
            if not isinstance(node, ast.ClassDef):
                return None
            node = next((item for item in reversed(node.body)
                         if getattr(item, "name", None) == part), None)
        return node

    def _value(self, symbol):
        self._tick()
        if isinstance(symbol, _Imported):
            return self._attr(_Symbol(symbol.path, absolute=symbol.absolute), symbol.name)
        module = self._module(symbol.path)
        if module is None:
            return UNKNOWN
        if not symbol.name:
            return symbol
        if (symbol.path, symbol.name) in self.invalidated_globals:
            return UNKNOWN
        if symbol.owner or symbol.definition:
            return symbol if isinstance(self._node(symbol), (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) else UNKNOWN
        cutoff = self.cutoffs.get(symbol.path, float("inf"))
        history = module.bindings.get(symbol.name, ())
        if any(line == cutoff for line, _ in history) and sum(line == cutoff for line, _ in history) > 1:
            return UNKNOWN
        binding = next(((line, value) for line, value in reversed(history) if line < cutoff), None)
        if binding is None:
            return UNKNOWN
        line, node = binding
        key = (symbol.path, symbol.name, line)
        if key in self.resolving or len(self.resolving) >= MAX_DEPTH:
            self._diagnostic("RESOLUTION_CYCLE", symbol.path)
            return UNKNOWN
        self.resolving.add(key)
        try:
            if isinstance(node, _Symbol):
                return self._value(node)
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                return _Symbol(symbol.path, symbol.name, definition=line)
            if isinstance(node, (ast.Assign, ast.AnnAssign)):
                previous = self.cutoffs.get(symbol.path)
                self.cutoffs[symbol.path] = line
                self.pure += 1
                try:
                    value = self._expr(node.value, {}, symbol.path)
                    targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                    env = {}
                    for target in targets:
                        self._assign(target, value, env, symbol.path)
                    resolved = env.get(symbol.name, UNKNOWN)
                    self._track_origin(resolved, ("module", symbol.path, symbol.name))
                    return resolved
                finally:
                    self.pure -= 1
                    if previous is None:
                        self.cutoffs.pop(symbol.path, None)
                    else:
                        self.cutoffs[symbol.path] = previous
            return node if not isinstance(node, ast.AST) else UNKNOWN
        finally:
            self.resolving.remove(key)

    def _entry_method(self, model):
        # Registry selects load_file, not constructor writes. Constructors may
        # nevertheless supply static instance configuration to the selected method.
        method = self._attr(model, "load_file")
        if isinstance(method, _Bound):
            return method
        if isinstance(method, _Symbol):
            declaration = self._node(method)
            if isinstance(declaration, (ast.FunctionDef, ast.AsyncFunctionDef)) and any(
                self._decorator(item, method.path) == "staticmethod" for item in declaration.decorator_list
            ):
                return method
        instance = self._construct(model, [], {}, pure=True)
        return self._attr(instance, "load_file")

    def _construct(self, model, args, kwargs, pure=False):
        instance = _Instance(model)
        if pure:
            self.pure += 1
        try:
            generated = self._generated_initializer(model)
            if generated is not None:
                if not self._initialize_config(instance, generated, args, kwargs, entry=pure):
                    return _OPAQUE
                return instance
            constructor = self._attr(instance, "__init__")
            if isinstance(constructor, _Bound):
                self._invoke(constructor, args, kwargs, entry=pure)
            elif (args or kwargs) and self._attr(model, "__table__") is UNKNOWN:
                # A class with no source-visible constructor cannot supply a
                # known instance field from an unmodeled constructor argument.
                instance.attrs[_MISSING] = UNKNOWN
            return instance
        finally:
            if pure:
                self.pure -= 1

    def _config_kind(self, owner):
        if owner in self.generated_configs:
            return self.generated_configs[owner]
        node = self._node(owner)
        previous = self.cutoffs.get(owner.path)
        self.cutoffs[owner.path] = node.lineno
        self.pure += 1
        result = None
        try:
            for decorator in node.decorator_list:
                expression = decorator.func if isinstance(decorator, ast.Call) else decorator
                value = self._expr(expression, {}, owner.path)
                if isinstance(value, _External) and value.name == "dataclasses.dataclass":
                    options = {}
                    if isinstance(decorator, ast.Call):
                        if decorator.args or any(item.arg is None for item in decorator.keywords):
                            options["init"] = UNKNOWN
                        else:
                            options = {item.arg: self._expr(item.value, {}, owner.path) for item in decorator.keywords}
                    result = ("dataclass", options)
                    break
            if result is None:
                for expression in node.bases:
                    value = self._expr(expression, {}, owner.path)
                    if isinstance(value, _External):
                        if value.name == "typing.NamedTuple":
                            result = ("namedtuple", {})
                            break
                        if value.name in {"enum.Enum", "enum.IntEnum", "enum.StrEnum"}:
                            result = ("enum", {})
                            break
        finally:
            self.pure -= 1
            if previous is None:
                self.cutoffs.pop(owner.path, None)
            else:
                self.cutoffs[owner.path] = previous
        self.generated_configs[owner] = result
        return result

    def _generated_initializer(self, model):
        chain = self._class_chain(model)
        if chain is None:
            return None
        for owner in chain:
            if not isinstance(owner, _Symbol):
                return None
            node = self._node(owner)
            if any(isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name == "__init__" for item in node.body):
                return None
            kind = self._config_kind(owner)
            if kind and kind[0] in {"dataclass", "namedtuple"} and kind[1].get("init", True) is not False:
                return owner, kind
        return None

    def _initialize_config(self, instance, initializer, args, kwargs, *, entry):
        owner, (kind, options) = initializer
        if options.get("init", True) is not True or type(options.get("kw_only", False)) is not bool:
            self._diagnostic("CALL_ARGUMENTS_UNKNOWN", owner.path, self._node(owner))
            return False
        chain = self._class_chain(owner) or []
        fields = {}
        for parent in reversed(chain):
            if not isinstance(parent, _Symbol):
                continue
            parent_kind = self._config_kind(parent)
            if not parent_kind or parent_kind[0] != kind:
                continue
            for item in self._node(parent).body:
                if not isinstance(item, ast.AnnAssign) or not isinstance(item.target, ast.Name):
                    continue
                name = item.target.id
                annotation = item.annotation.value if isinstance(item.annotation, ast.Subscript) else item.annotation
                resolved = self._expr(annotation, {}, parent.path) if isinstance(annotation, (ast.Name, ast.Attribute)) else UNKNOWN
                if isinstance(resolved, _External) and resolved.name in {"typing.ClassVar", "typing_extensions.ClassVar"}:
                    continue
                if isinstance(resolved, _External) and resolved.name == "dataclasses.InitVar":
                    self._diagnostic("CALL_ARGUMENTS_UNKNOWN", parent.path, item)
                    return False
                default = self._own_member(parent, name, instance.model) if item.value is not None else _MISSING
                if isinstance(default, _Field):
                    field_value = default
                    # Retain the factory until binding: a supplied argument
                    # suppresses its execution in a real dataclass constructor.
                    default = field_value
                    init = field_value.init
                    kw_only = parent_kind[1].get("kw_only", False) if field_value.kw_only is _MISSING else field_value.kw_only
                else:
                    init = True
                    kw_only = parent_kind[1].get("kw_only", False)
                if type(init) is not bool or type(kw_only) is not bool:
                    self._diagnostic("CALL_ARGUMENTS_UNKNOWN", parent.path, item)
                    return False
                fields[name] = (default, init, kw_only)
                if len(fields) > MAX_ITEMS:
                    raise _Limit()
        positional = [name for name, (_, init, kw_only) in fields.items() if init and not kw_only]
        if len(args) > len(positional) or any(name not in fields or not fields[name][1] for name in kwargs):
            self._diagnostic("CALL_ARGUMENTS_UNKNOWN", owner.path, self._node(owner))
            return False
        bound = dict(zip(positional, args))
        if bound.keys() & kwargs.keys():
            self._diagnostic("CALL_ARGUMENTS_UNKNOWN", owner.path, self._node(owner))
            return False
        bound.update(kwargs)
        for name, (default, init, _) in fields.items():
            if name in bound:
                value = bound[name]
            elif isinstance(default, _Field):
                if default.factory is not _MISSING:
                    factory = default.factory
                    value = self._invoke(factory, [], {}) if isinstance(factory, (_Symbol, _Bound)) else UNKNOWN
                elif default.default is not _MISSING:
                    value = default.default
                elif entry or not init:
                    value = UNKNOWN
                else:
                    self._diagnostic("CALL_ARGUMENTS_UNKNOWN", owner.path, self._node(owner))
                    return False
            elif default is not _MISSING:
                value = default
            elif entry or not init:
                value = UNKNOWN
            else:
                self._diagnostic("CALL_ARGUMENTS_UNKNOWN", owner.path, self._node(owner))
                return False
            instance.attrs[name] = value
        if kind == "dataclass":
            post_init = self._attr(instance, "__post_init__")
            if isinstance(post_init, _Bound):
                self._invoke(post_init, [], {})
        return True

    def _class_symbol(self, value):
        if isinstance(value, _Instance):
            return value.model
        return value if isinstance(value, _Symbol) and isinstance(self._node(value), ast.ClassDef) else None

    def _class_chain(self, value, seen=None):
        """C3 order for source-visible classes; reject inconsistent hierarchies."""
        self._tick()
        seen = set() if seen is None else seen
        if value in seen or len(seen) >= MAX_DEPTH:
            self._diagnostic("RESOLUTION_CYCLE", value.path)
            return None
        node = self._node(value)
        if not isinstance(node, ast.ClassDef):
            return None
        if value in self.mro_cache:
            return self.mro_cache[value]
        seen = seen | {value}
        bases = []
        previous = self.cutoffs.get(value.path)
        self.cutoffs[value.path] = node.lineno
        try:
            for expression in node.bases:
                base = self._expr(expression, {}, value.path)
                # Generic Base[T] has the same lookup base for our source model.
                if base is UNKNOWN and isinstance(expression, ast.Subscript):
                    base = self._expr(expression.value, {}, value.path)
                if isinstance(base, _Symbol) and isinstance(self._node(base), ast.ClassDef):
                    bases.append(base)
                elif isinstance(base, _Base):
                    bases.append(base)
                elif isinstance(base, _External) and base.name in {"sqlalchemy.orm.DeclarativeBase", "sqlalchemy.orm.decl_api.DeclarativeBase", "typing.Generic", "typing.Protocol", "abc.ABC", "typing.NamedTuple", "enum.Enum", "enum.IntEnum", "enum.StrEnum"}:
                    continue
                elif isinstance(expression, ast.Name) and expression.id == "object" and base is UNKNOWN:
                    continue
                else:
                    # An opaque base can shadow later members; do not choose them.
                    bases.append(_External("<opaque_base>"))
        finally:
            if previous is None:
                self.cutoffs.pop(value.path, None)
            else:
                self.cutoffs[value.path] = previous
        sequences = []
        for base in bases:
            chain = self._class_chain(base, seen) if isinstance(base, _Symbol) else [base]
            if chain is None:
                return None
            sequences.append(list(chain))
        sequences.append(list(bases))
        result = [value]
        while any(sequences):
            self._tick()
            candidate = next((seq[0] for seq in sequences if seq and
                              not any(seq[0] in other[1:] for other in sequences)), None)
            if candidate is None:
                self._diagnostic("INHERITANCE_UNRESOLVED", value.path, node)
                return None
            result.append(candidate)
            for seq in sequences:
                if seq and seq[0] == candidate:
                    seq.pop(0)
            if len(result) > MAX_ITEMS:
                raise _Limit()
        self.mro_cache[value] = result
        return result

    def _decorator(self, node, path):
        if isinstance(node, ast.Name) and node.id in {"classmethod", "staticmethod", "property"}:
            module = self._module(path)
            if not module or node.id not in module.bindings:
                return node.id
        value = self._expr(node, {}, path)
        if isinstance(value, _External):
            if value.name in {"builtins.classmethod", "builtins.staticmethod", "builtins.property"}:
                return value.name.rsplit(".", 1)[1]
            if value.name in {
                "sqlalchemy.orm.declared_attr", "sqlalchemy.orm.decl_api.declared_attr",
                "sqlalchemy.orm.declared_attr.directive", "sqlalchemy.orm.declared_attr.cascading",
                "sqlalchemy.orm.decl_api.declared_attr.directive", "sqlalchemy.orm.decl_api.declared_attr.cascading",
            }:
                return "declared_attr"
        return None

    def _own_member(self, owner, name, receiver):
        node = self._node(owner)
        class_env = {}
        # Class bodies evaluate in definition order and in module definition scope.
        previous = self.cutoffs.get(owner.path)
        self.cutoffs[owner.path] = node.lineno
        self.pure += 1
        try:
            for item in node.body:
                self._tick()
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    function = _Symbol(owner.path, item.name, ".".join(filter(None, [owner.owner, owner.name])), definition=owner.definition)
                    decorators = {self._decorator(d, owner.path) for d in item.decorator_list}
                    class_env[item.name] = (function, decorators)
                elif isinstance(item, ast.ClassDef):
                    class_env[item.name] = _Symbol(owner.path, item.name, ".".join(filter(None, [owner.owner, owner.name])), definition=owner.definition)
                elif isinstance(item, (ast.Assign, ast.AnnAssign)) and item.value is not None:
                    targets = item.targets if isinstance(item, ast.Assign) else [item.target]
                    resolved = self._expr(item.value, class_env, owner.path)
                    for target in targets:
                        self._assign(target, resolved, class_env, owner.path)
                elif isinstance(item, (ast.If, ast.Try, ast.For, ast.While, ast.With)):
                    for child in ast.walk(item):
                        if isinstance(child, ast.Name) and isinstance(child.ctx, ast.Store):
                            class_env[child.id] = UNKNOWN
                        elif isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                            class_env[child.name] = UNKNOWN
            found = class_env.get(name, _MISSING)
        finally:
            self.pure -= 1
            if previous is None:
                self.cutoffs.pop(owner.path, None)
            else:
                self.cutoffs[owner.path] = previous
        if isinstance(found, tuple) and len(found) == 2 and isinstance(found[0], _Symbol) and isinstance(found[1], set):
            function, decorators = found
            model = self._class_symbol(receiver)
            if None in decorators:
                return UNKNOWN
            if "declared_attr" in decorators or ("property" in decorators and isinstance(receiver, _Instance)):
                self.pure += 1
                try:
                    return self._invoke(_Bound(function, model if "declared_attr" in decorators else receiver), [], {})
                finally:
                    self.pure -= 1
            if "property" in decorators:
                return UNKNOWN
            if "staticmethod" in decorators:
                return function
            if "classmethod" in decorators:
                return _Bound(function, model)
            return _Bound(function, receiver) if isinstance(receiver, _Instance) else function
        kind = self._config_kind(owner)
        if kind and kind[0] == "enum" and not name.startswith("_") and isinstance(found, (str, int, tuple)):
            return _EnumMember(name, found)
        return found

    def _class_member(self, receiver, name, *, after=None):
        model = self._class_symbol(receiver)
        if model is None:
            return _MISSING
        chain = self._class_chain(model)
        if chain is None:
            return UNKNOWN
        if after is not None:
            index = next((i for i, item in enumerate(chain) if isinstance(item, _Symbol)
                          and (item.path, item.name, item.owner, item.definition) == (after.path, after.name, after.owner, after.definition)), None)
            if index is None:
                return UNKNOWN
            chain = chain[index + 1:]
        for base in chain:
            if isinstance(base, _Base):
                if name == "metadata":
                    return base.metadata
                continue
            if isinstance(base, _External):
                # Unknown base may declare this member. Never fall through to
                # a known but lower-precedence base or an unqualified schema.
                return UNKNOWN
            if (base, name) in self.invalidated_members:
                return UNKNOWN
            found = self._own_member(base, name, receiver)
            if found is not _MISSING:
                self._track_origin(found, ("class", base, name))
                return found
        return _MISSING

    def _attr(self, value, name, seen=None):
        self._tick()
        if value is _BLOCKED_IMPORT or value is _OPAQUE:
            return value
        if isinstance(value, _OrmTable):
            if name == "name":
                return self._attr(value.model, "__tablename__")
            if name == "schema":
                return self._orm_schema(value.model)
            if name == "fullname":
                schema, table = self._orm_schema(value.model), self._attr(value.model, "__tablename__")
                return self._fullname(schema, table)
            if name in {"insert", "update", "delete", "select"}:
                return _Method(value, name)
            return UNKNOWN
        if isinstance(value, _Table):
            if name in {"name", "schema"}:
                return getattr(value, name)
            if name == "fullname":
                return self._fullname(value.schema, value.name)
            if name in {"insert", "update", "delete", "select"}:
                return _Method(value, name)
            return UNKNOWN
        if isinstance(value, (_Receiver, _Dml, _SqlFragment, _SqlText, _OrmQuery, _ReadStatement)):
            return _Method(value, name)
        if isinstance(value, _EnumMember):
            return value.value if name == "value" else value.name if name == "name" else UNKNOWN
        if isinstance(value, _Metadata):
            return value.schema if name == "schema" else UNKNOWN
        if isinstance(value, _Base):
            return value.metadata if name == "metadata" else UNKNOWN
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
            found = self._class_member(value.receiver, name, after=value.owner)
            return UNKNOWN if found is _MISSING else found
        if isinstance(value, _Symbol) and not value.name:
            found = self._value(_Symbol(value.path, name))
            if found is UNKNOWN:
                module = self._module(value.path)
                # An explicitly declared but unresolved value is not a submodule.
                if module and name in module.bindings:
                    return UNKNOWN
                if module and value.path.name == "__init__.py":
                    if value.absolute:
                        spec = f"{value.absolute}.{name}"
                        try:
                            nested = self.sources.resolve(spec)
                        except AmbiguousModule:
                            self._diagnostic("MODULE_AMBIGUOUS", value.path)
                            return _BLOCKED_IMPORT
                        return _Symbol(nested, absolute=spec) if nested else UNKNOWN
                    nested = self.sources.resolve(name, value.path, 1)
                    return _Symbol(nested) if nested else UNKNOWN
            return found
        model = self._class_symbol(value)
        if model is None:
            return UNKNOWN
        if isinstance(value, _Instance):
            if name == "__class__":
                return model
            if name in value.attrs:
                return value.attrs[name]
            if _MISSING in value.attrs:
                return UNKNOWN
        if name == "__name__" and not isinstance(value, _Instance):
            return model.name
        key = (model.path, model.owner, model.name, name, "member")
        if key in self.resolving or len(self.resolving) >= MAX_DEPTH:
            self._diagnostic("RESOLUTION_CYCLE", model.path)
            return UNKNOWN
        self.resolving.add(key)
        try:
            found = self._class_member(value, name)
            if found is _MISSING and name == "__table__":
                tablename = self._attr(model, "__tablename__")
                if isinstance(tablename, str):
                    return _OrmTable(model)
            if isinstance(found, _Field):
                return found.default if found.default is not _MISSING else UNKNOWN
            return UNKNOWN if found is _MISSING else found
        finally:
            self.resolving.remove(key)

    @staticmethod
    def _fullname(schema, table):
        if not isinstance(table, str) or (schema is not None and not isinstance(schema, str)):
            return UNKNOWN
        return f"{schema}.{table}" if schema else table

    def _expr(self, node, env, path):
        self._tick()
        if isinstance(node, ast.Constant):
            return node.value if isinstance(node.value, (str, int, bool, type(None))) else UNKNOWN
        if isinstance(node, ast.Name):
            if node.id in env:
                return env[node.id]
            if node.id == "__name__" and node.id not in self._module(path).bindings:
                root = self.sources.owner(path)
                if root:
                    relative = path.relative_to(root).with_suffix("")
                    return ".".join(part for part in relative.parts if part != "__init__")
            return self._value(_Symbol(path, node.id))
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
            if len(values) > MAX_ITEMS:
                raise _Limit()
            return tuple(values)
        if isinstance(node, ast.Dict):
            if len(node.keys) > MAX_ITEMS:
                raise _Limit()
            result = {}
            for key, value in zip(node.keys, node.values):
                v = self._expr(value, env, path)
                if key is None:
                    if not isinstance(v, dict):
                        return UNKNOWN
                    result.update(v)
                else:
                    k = self._expr(key, env, path)
                    if not isinstance(k, (str, int, tuple)):
                        return UNKNOWN
                    try:
                        result[k] = v
                    except TypeError:
                        return UNKNOWN
                if len(result) > MAX_ITEMS:
                    raise _Limit()
            return result
        if isinstance(node, ast.ListComp):
            return self._list_comprehension(node, env, path)
        if isinstance(node, ast.Subscript):
            value = self._expr(node.value, env, path)
            key = self._expr(node.slice, env, path)
            try:
                if isinstance(value, str) and _UNKNOWN_TEXT.lower() in value.lower():
                    return UNKNOWN
                return value[key] if isinstance(value, (dict, tuple, str)) else UNKNOWN
            except (KeyError, IndexError, TypeError):
                return UNKNOWN
        if isinstance(node, ast.JoinedStr):
            parts = []
            for item in node.values:
                if isinstance(item, ast.FormattedValue):
                    value = self._expr(item.value, env, path)
                    spec = self._expr(item.format_spec, env, path) if item.format_spec else ""
                    value = self._format_value(value, spec, item.conversion)
                else:
                    value = self._expr(item, env, path)
                parts.append(value if isinstance(value, str) else _UNKNOWN_TEXT)
            return self._text("".join(parts))
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            operand = self._expr(node.operand, env, path)
            return not operand if self._known_truth(operand) else UNKNOWN
        if isinstance(node, ast.BoolOp):
            # Python short-circuits; do not visit provably unreachable operands.
            for index, operand in enumerate(node.values):
                value = self._expr(operand, env, path)
                if not self._known_truth(value):
                    self._diagnostic("CONTROL_FLOW_UNKNOWN", path, node)
                    return UNKNOWN
                if index == len(node.values) - 1 or (
                    isinstance(node.op, ast.And) and not value
                ) or (isinstance(node.op, ast.Or) and value):
                    return value
        if isinstance(node, ast.IfExp):
            test = self._expr(node.test, env, path)
            if self._known_truth(test):
                return self._expr(node.body if test else node.orelse, env, path)
            self._diagnostic("CONTROL_FLOW_UNKNOWN", path, node)
            return UNKNOWN
        if isinstance(node, ast.Compare) and len(node.ops) == 1:
            left = self._expr(node.left, env, path)
            right = self._expr(node.comparators[0], env, path)
            if type(left) in (str, int, bool, type(None)) and type(right) in (
                str, int, bool, type(None)
            ):
                if isinstance(node.ops[0], ast.Eq):
                    return left == right
                if isinstance(node.ops[0], ast.NotEq):
                    return left != right
            return UNKNOWN
        if isinstance(node, ast.BinOp):
            left, right = self._expr(node.left, env, path), self._expr(node.right, env, path)
            if isinstance(node.op, ast.Add):
                if isinstance(left, str) and isinstance(right, str):
                    return self._text(left + right)
                if isinstance(left, tuple) and isinstance(right, tuple):
                    if len(left) + len(right) > MAX_ITEMS:
                        raise _Limit()
                    return left + right
                if isinstance(left, _SqlFragment) and isinstance(right, _SqlFragment):
                    return _SqlFragment(self._text(left.text + right.text))
            if isinstance(node.op, ast.BitOr) and isinstance(left, dict) and isinstance(right, dict):
                result = {**left, **right}
                if len(result) > MAX_ITEMS:
                    raise _Limit()
                return result
            if isinstance(node.op, ast.Mod) and isinstance(left, str):
                return self._percent_format(left, right)
            return UNKNOWN
        if isinstance(node, ast.Call):
            return self._call(node, env, path)
        if isinstance(node, ast.Await):
            return self._expr(node.value, env, path)
        if isinstance(node, ast.NamedExpr):
            value = self._expr(node.value, env, path)
            self._assign(node.target, value, env, path)
            return value
        # An unsupported expression can contain lazy/unreachable calls. Do not
        # walk it as if every nested call were executed.
        if node is not None and isinstance(node, ast.expr):
            self._diagnostic("EXPRESSION_UNSUPPORTED", path, node)
        return UNKNOWN

    def _list_comprehension(self, node, env, path):
        result = []
        def visit(index, local):
            if index == len(node.generators):
                result.append(self._expr(node.elt, local, path))
                if len(result) > MAX_ITEMS:
                    raise _Limit()
                return
            generator = node.generators[index]
            values = self._expr(generator.iter, local, path)
            if isinstance(values, dict):
                values = tuple(values)
            if not isinstance(values, tuple):
                self._diagnostic("DYNAMIC_LOOP", path, node)
                values = (UNKNOWN,)
            for value in values:
                self.iterations += 1
                if self.iterations > MAX_ITERATIONS:
                    raise _Limit()
                scope = dict(local)
                self._assign(generator.target, value, scope, path)
                include = True
                for condition in generator.ifs:
                    test = self._expr(condition, scope, path)
                    if self._known_truth(test) and not test:
                        include = False
                        break
                    if not self._known_truth(test):
                        self._diagnostic("CONTROL_FLOW_UNKNOWN", path, node)
                if include:
                    visit(index + 1, scope)
        visit(0, dict(env))
        return tuple(result)

    @staticmethod
    def _text(value):
        if len(value) > MAX_TEXT:
            raise _Limit()
        return value

    def _format_value(self, value, spec="", conversion=-1):
        if type(value) not in (str, int, bool, type(None)) or not isinstance(spec, str):
            return UNKNOWN
        if isinstance(value, str) and _UNKNOWN_TEXT.lower() in value.lower():
            return UNKNOWN
        # Only a small, bounded subset of built-in formatting. No arbitrary
        # attribute access, dynamic format protocols or excessive field widths.
        if len(spec) > 32 or any(int(n) > 1024 for n in re.findall(r"[0-9]+", spec)):
            return UNKNOWN
        try:
            if conversion == ord("r"):
                value = repr(value)
            elif conversion == ord("a"):
                value = ascii(value)
            elif conversion == ord("s"):
                value = str(value)
            elif conversion != -1:
                return UNKNOWN
            return self._text(format(value, spec))
        except (ValueError, TypeError, OverflowError):
            return UNKNOWN

    def _format_text(self, template, args, kwargs, *, sql=False):
        parts = []
        auto = 0
        auto_used = manual_used = False
        try:
            for literal, field, spec, conversion in string.Formatter().parse(template):
                parts.append(literal)
                if field is None:
                    continue
                if not field:
                    auto_used = True
                    field = str(auto)
                    auto += 1
                elif field.isdecimal():
                    manual_used = True
                if auto_used and manual_used:
                    return UNKNOWN
                if field.isdecimal():
                    if len(field) > 6:
                        return UNKNOWN
                    index = int(field)
                    if index >= len(args):
                        return UNKNOWN
                    value = args[index]
                elif field.isidentifier():
                    if field not in kwargs:
                        return UNKNOWN
                    value = kwargs[field]
                else:
                    # Do not invoke Python attribute or item formatting hooks.
                    return UNKNOWN
                if sql:
                    if spec or conversion:
                        return UNKNOWN
                    value = value.text if isinstance(value, _SqlFragment) else UNKNOWN
                else:
                    value = self._format_value(value, spec, ord(conversion) if conversion else -1)
                parts.append(value if isinstance(value, str) else _UNKNOWN_TEXT)
                if len(parts) > MAX_ITEMS * 2:
                    raise _Limit()
            return self._text("".join(parts))
        except (ValueError, TypeError, IndexError, OverflowError):
            return UNKNOWN

    def _percent_format(self, template, values):
        # Old-style % interpolation is common in ETL, but only simple %s/%d
        # and mapping substitutions are modeled. SQL placeholders not used in
        # Python interpolation are left untouched by the SQL recognizer.
        parts = []
        position = index = 0
        args = values if isinstance(values, tuple) else (values,)
        mapping = values if isinstance(values, dict) else None
        for match in re.finditer(r"%(%|(?:\(([A-Za-z_][A-Za-z_0-9]*)\))?([sd]))", template):
            if "%" in template[position:match.start()]:
                return UNKNOWN
            parts.append(template[position:match.start()])
            if match.group(1) == "%":
                parts.append("%")
            else:
                key = match.group(2)
                if key:
                    if mapping is None or key not in mapping:
                        return UNKNOWN
                    value = mapping[key]
                else:
                    if index >= len(args):
                        return UNKNOWN
                    value = args[index]
                    index += 1
                if match.group(3) == "d" and type(value) not in (int, bool):
                    value = UNKNOWN
                value = self._format_value(value, "", ord("s"))
                parts.append(value if isinstance(value, str) else _UNKNOWN_TEXT)
            position = match.end()
            if len(parts) > MAX_ITEMS * 2:
                raise _Limit()
        if "%" in template[position:] or (mapping is None and index != len(args)):
            return UNKNOWN
        parts.append(template[position:])
        return self._text("".join(parts))

    def _dict_call(self, owner, name, args, kwargs):
        if name == "get" and len(args) in (1, 2) and not kwargs:
            try:
                return owner.get(args[0], UNKNOWN if _MISSING in owner else args[1] if len(args) > 1 else None)
            except TypeError:
                return UNKNOWN
        if name in {"items", "keys", "values", "copy"} and not args and not kwargs:
            return owner.copy() if name == "copy" else tuple(getattr(owner, name)())
        if name == "update":
            self._mark_mutated(owner)
            if len(args) > 1 or (args and not isinstance(args[0], dict)):
                self._invalidate_dict(owner)
            elif args:
                if _MISSING in args[0]:
                    self._invalidate_dict(owner)
                owner.update(args[0])
            owner.update(kwargs)
            if len(owner) > MAX_ITEMS:
                raise _Limit()
            return None
        if name == "clear" and not args and not kwargs:
            self._mark_mutated(owner)
            owner.clear()
            return None
        if name in {"setdefault", "pop"} and len(args) in (1, 2) and not kwargs:
            self._mark_mutated(owner)
            try:
                if _MISSING in owner and args[0] not in owner:
                    return UNKNOWN
                if name == "setdefault":
                    if len(owner) >= MAX_ITEMS and args[0] not in owner:
                        raise _Limit()
                    return owner.setdefault(*args)
                return owner.pop(*args)
            except (KeyError, TypeError):
                return UNKNOWN
        if name == "popitem" and not args and not kwargs:
            self._mark_mutated(owner)
            if _MISSING in owner:
                self._invalidate_dict(owner)
                return UNKNOWN
            return owner.popitem() if owner else UNKNOWN
        return _OPAQUE

    def _string_call(self, owner, name, args, kwargs):
        if name == "format":
            return self._format_text(owner, args, kwargs)
        if name == "format_map" and len(args) == 1 and isinstance(args[0], dict) and not kwargs:
            return self._format_text(owner, [], args[0])
        if kwargs:
            return UNKNOWN
        if name in {"lower", "upper", "casefold", "capitalize", "title"} and not args:
            return self._text(getattr(owner, name)())
        if name in {"strip", "lstrip", "rstrip"} and len(args) <= 1 and all(isinstance(a, str) for a in args):
            return getattr(owner, name)(*args)
        if name in {"removeprefix", "removesuffix"} and len(args) == 1 and isinstance(args[0], str):
            return getattr(owner, name)(args[0])
        if name == "replace" and len(args) in (2, 3) and all(isinstance(a, str) for a in args[:2]):
            count = args[2] if len(args) == 3 else -1
            if type(count) is not int:
                return UNKNOWN
            hits = owner.count(args[0]) if count < 0 else min(owner.count(args[0]), count)
            if len(owner) + hits * max(0, len(args[1]) - len(args[0])) > MAX_TEXT:
                raise _Limit()
            return owner.replace(args[0], args[1], count)
        if name == "join" and len(args) == 1 and isinstance(args[0], tuple) and all(isinstance(a, str) for a in args[0]):
            if sum(map(len, args[0])) + len(owner) * max(0, len(args[0]) - 1) > MAX_TEXT:
                raise _Limit()
            return owner.join(args[0])
        if name in {"split", "rsplit"} and len(args) <= 2:
            sep = args[0] if args else None
            limit = args[1] if len(args) == 2 else -1
            if (sep is None or isinstance(sep, str)) and sep != "" and type(limit) is int:
                parts = getattr(owner, name)(sep, min(limit, MAX_ITEMS) if limit >= 0 else MAX_ITEMS)
                if len(parts) > MAX_ITEMS:
                    raise _Limit()
                return tuple(parts)
        return UNKNOWN

    @staticmethod
    def _argument(args, kwargs, name, position, default=UNKNOWN):
        if name in kwargs:
            return kwargs[name] if position >= len(args) else UNKNOWN
        return args[position] if position < len(args) else default

    @staticmethod
    def _external_receiver(name):
        if name in {"pandas.DataFrame", "pandas.core.frame.DataFrame"} or name in {
            "pandas.read_csv", "pandas.read_excel", "pandas.read_parquet", "pandas.read_sql",
            "pandas.read_sql_query", "pandas.read_sql_table", "pandas.read_json", "pandas.concat",
        }:
            return _Receiver("dataframe")
        if name in {"sqlalchemy.create_engine", "sqlalchemy.engine.create_engine", "sqlalchemy.engine.Engine"}:
            return _Receiver("engine")
        if name in {"sqlalchemy.orm.Session", "sqlalchemy.orm.session.Session", "sqlalchemy.ext.asyncio.AsyncSession"}:
            return _Receiver("session")
        if name in {"sqlalchemy.orm.sessionmaker", "sqlalchemy.orm.session.sessionmaker", "sqlalchemy.orm.scoped_session", "sqlalchemy.ext.asyncio.async_sessionmaker"}:
            return _Receiver("session_factory")
        if name in {"sqlalchemy.engine.Connection", "sqlalchemy.engine.base.Connection", "psycopg.connect", "psycopg2.connect", "psycopg.Connection", "psycopg2.extensions.connection", "psycopg.AsyncConnection.connect"}:
            return _Receiver("connection")
        if name in {"psycopg.Cursor", "psycopg.AsyncCursor", "psycopg2.extensions.cursor"}:
            return _Receiver("cursor")
        return UNKNOWN

    def _external_call(self, function, args, kwargs, path, node):
        name = function.name
        arg = self._argument
        receiver = self._external_receiver(name)
        if receiver is not UNKNOWN:
            return receiver
        if name == "dataclasses.field" and not args:
            return _Field(kwargs.get("default", _MISSING), kwargs.get("default_factory", _MISSING), kwargs.get("init", True), kwargs.get("kw_only", _MISSING))
        if name in {f"{prefix}.{constraint}" for prefix in ("sqlalchemy", "sqlalchemy.schema", "sqlalchemy.sql.schema") for constraint in ("UniqueConstraint", "CheckConstraint", "PrimaryKeyConstraint", "ForeignKeyConstraint", "Index") }:
            return _Constraint()
        if name in {"sqlalchemy.MetaData", "sqlalchemy.schema.MetaData", "sqlalchemy.sql.schema.MetaData"}:
            return _Metadata(arg(args, kwargs, "schema", 0, None))
        if name in {"sqlalchemy.Table", "sqlalchemy.schema.Table", "sqlalchemy.sql.schema.Table"}:
            table = arg(args, kwargs, "name", 0)
            metadata = arg(args, kwargs, "metadata", 1)
            schema = kwargs.get("schema", metadata.schema if isinstance(metadata, _Metadata) else UNKNOWN)
            if schema is None and isinstance(metadata, _Metadata):
                schema = metadata.schema
            return _Table(schema, table)
        if name in {"sqlalchemy.orm.declarative_base", "sqlalchemy.ext.declarative.declarative_base", "sqlalchemy.orm.decl_api.declarative_base"}:
            metadata = kwargs.get("metadata", _Metadata(None))
            return _Base(metadata if isinstance(metadata, _Metadata) else _Metadata(UNKNOWN))
        if name in {"sqlalchemy.insert", "sqlalchemy.update", "sqlalchemy.delete", "sqlalchemy.sql.insert", "sqlalchemy.sql.update", "sqlalchemy.sql.delete", "sqlalchemy.sql.dml.insert", "sqlalchemy.sql.dml.update", "sqlalchemy.sql.dml.delete", "sqlalchemy.dialects.postgresql.insert", "sqlalchemy.dialects.postgresql.dml.insert"}:
            return _Dml(arg(args, kwargs, "table", 0))
        if name in {"sqlalchemy.select", "sqlalchemy.sql.select", "sqlalchemy.sql.expression.select"}:
            return _ReadStatement()
        if name in {"sqlalchemy.text", "sqlalchemy.sql.text", "sqlalchemy.sql.expression.text"}:
            value = arg(args, kwargs, "text", 0)
            return _SqlText(value) if isinstance(value, str) else UNKNOWN
        if name in {"psycopg.sql.SQL", "psycopg2.sql.SQL"}:
            value = arg(args, kwargs, "string", 0)
            return _SqlFragment(value) if isinstance(value, str) else UNKNOWN
        if name in {"psycopg.sql.Identifier", "psycopg2.sql.Identifier"}:
            if not args or kwargs:
                return UNKNOWN
            parts = []
            for value in args:
                if not isinstance(value, str):
                    value = _UNKNOWN_TEXT
                parts.append('"' + value.replace('"', '""') + '"')
            return _SqlFragment(self._text(".".join(parts)))
        if name in {"psycopg.sql.Literal", "psycopg2.sql.Literal", "psycopg.sql.Placeholder", "psycopg2.sql.Placeholder"}:
            # Literals never supply relation identifiers.
            return _SqlFragment("'" + _UNKNOWN_TEXT + "'")
        if name in {"psycopg2.extras.execute_values", "psycopg2.extras.execute_batch"}:
            if not self.pure:
                self._sql(arg(args, kwargs, "sql", 1), path, node)
            return UNKNOWN
        if name in {"pandas.io.sql.to_sql", "pandas.DataFrame.to_sql", "pandas.core.frame.DataFrame.to_sql"}:
            if not self.pure:
                self._write(kwargs.get("schema", args[3] if len(args) > 3 else None), arg(args, kwargs, "name", 1), path, node, "to_sql")
            return UNKNOWN
        return UNKNOWN

    def _call(self, node, env, path):
        name = node.func.attr if isinstance(node.func, ast.Attribute) else getattr(node.func, "id", "")
        owner = self._expr(node.func.value, env, path) if isinstance(node.func, ast.Attribute) else UNKNOWN
        function = self._attr(owner, name) if isinstance(node.func, ast.Attribute) else self._expr(node.func, env, path)
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
                if item.arg in kwargs:
                    self._diagnostic("CALL_ARGUMENTS_UNKNOWN", path, node)
                    return UNKNOWN
                kwargs[item.arg] = value
            elif isinstance(value, dict) and all(isinstance(key, str) for key in value):
                if kwargs.keys() & value.keys():
                    self._diagnostic("CALL_ARGUMENTS_UNKNOWN", path, node)
                    return UNKNOWN
                kwargs.update(value)
            else:
                self._diagnostic("CALL_ARGUMENTS_UNKNOWN", path, node)
                return UNKNOWN
        if len(args) + len(kwargs) > MAX_ITEMS:
            raise _Limit()
        if owner is _BLOCKED_IMPORT or function is _BLOCKED_IMPORT:
            return _BLOCKED_IMPORT
        if owner is _OPAQUE or function is _OPAQUE:
            return _OPAQUE
        if isinstance(node.func, ast.Name) and function is UNKNOWN and name not in env and name not in self._module(path).bindings:
            if name == "super" and self.stack:
                current = self.stack[-1]
                declaration = self._node(current)
                params = declaration.args.posonlyargs + declaration.args.args
                receiver = env.get(params[0].arg, UNKNOWN) if params else UNKNOWN
                if len(args) == 2 and not kwargs:
                    base, receiver = args
                    if self._class_symbol(base) and self._class_symbol(receiver):
                        return _Super(base, receiver)
                elif not args and not kwargs and current.owner and self._class_symbol(receiver):
                    owner_parts = current.owner.split(".")
                    base = _Symbol(current.path, owner_parts[-1], ".".join(owner_parts[:-1]), definition=current.definition)
                    return _Super(base, receiver)
            if name == "getattr" and len(args) in (2, 3) and isinstance(args[1], str) and not kwargs:
                # A default applies only to a known absent member, not an unknown value.
                if len(args) == 3 and self._class_symbol(args[0]) and self._class_member(args[0], args[1]) is _MISSING:
                    if not isinstance(args[0], _Instance) or args[1] not in args[0].attrs:
                        return args[2]
                return self._attr(args[0], args[1])
            if name == "type" and len(args) == 1 and not kwargs and isinstance(args[0], _Instance):
                return args[0].model
            if name == "str" and len(args) == 1 and not kwargs:
                return self._format_value(args[0], "", ord("s"))
            if name == "dict" and len(args) <= 1 and (not args or isinstance(args[0], dict)):
                value = {**(args[0] if args else {}), **kwargs}
                if len(value) > MAX_ITEMS:
                    raise _Limit()
                return value
            if name in {"tuple", "list"} and len(args) <= 1 and not kwargs:
                return tuple(args[0]) if args and isinstance(args[0], (tuple, dict)) else () if not args else UNKNOWN
            if name == "zip" and all(isinstance(value, tuple) for value in args) and not kwargs:
                return tuple(zip(*args))
            if name == "enumerate" and len(args) in (1, 2) and isinstance(args[0], tuple) and not kwargs and (len(args) == 1 or type(args[1]) is int):
                return tuple(enumerate(args[0], args[1] if len(args) == 2 else 0))
            if name == "range" and 1 <= len(args) <= 3 and all(type(value) is int for value in args) and not kwargs:
                try:
                    values = range(*args)
                    if len(values) > MAX_ITEMS:
                        raise _Limit()
                    return tuple(values)
                except (ValueError, OverflowError):
                    return UNKNOWN
        if isinstance(owner, dict):
            return self._dict_call(owner, name, args, kwargs)
        if isinstance(owner, str):
            if _UNKNOWN_TEXT.lower() in owner.lower() and name not in {"format", "format_map"}:
                return UNKNOWN
            return self._string_call(owner, name, args, kwargs)
        if isinstance(function, (_Symbol, _Bound)):
            symbol = function.function if isinstance(function, _Bound) else function
            if isinstance(self._node(symbol), ast.ClassDef):
                return self._construct(symbol, args, kwargs)
            return self._invoke(function, args, kwargs)
        if isinstance(function, _External):
            result = self._external_call(function, args, kwargs, path, node)
            if result is UNKNOWN and not self.pure and function.name not in {"psycopg2.extras.execute_values", "psycopg2.extras.execute_batch", "pandas.io.sql.to_sql", "pandas.DataFrame.to_sql", "pandas.core.frame.DataFrame.to_sql"}:
                self._forget_arguments([*args, *kwargs.values()])
            return result
        if isinstance(function, _Method):
            return self._method_call(function.receiver, function.name, args, kwargs, path, node)
        if isinstance(function, _Receiver) and function.kind == "session_factory":
            return _Receiver("session")
        if self.pure:
            return UNKNOWN
        # Legacy untyped dataframe/cursor arguments remain supported. Do not
        # guess writes for known non-writer objects, including local classes.
        if owner is UNKNOWN and isinstance(node.func, ast.Attribute):
            if name not in {"to_sql", "execute", "executemany", "exec_driver_sql", "copy_expert", "copy_from", "copy", "add", "add_all", "bulk_insert_mappings", "bulk_update_mappings", "bulk_save_objects", "delete", "merge"}:
                self._forget_arguments([*args, *kwargs.values()])
            return self._method_call(owner, name, args, kwargs, path, node)
        if isinstance(owner, (_Symbol, _Instance, _Namespace, _Super, _Metadata, _Base)):
            self._forget_arguments([owner, *args, *kwargs.values()])
            return _OPAQUE
        if function is UNKNOWN and name not in {"super", "getattr", "type", "str", "dict"}:
            self._forget_arguments([*args, *kwargs.values()])
        return UNKNOWN

    def _forget_arguments(self, values):
        if self.pure:
            return
        seen = set()
        def forget(value):
            if id(value) in seen:
                return
            seen.add(id(value))
            self._tick()
            if isinstance(value, dict):
                self._mark_mutated(value)
                for item in tuple(value.values()):
                    forget(item)
                self._invalidate_dict(value)
            elif isinstance(value, _Instance):
                self._mark_mutated(value)
                for item in tuple(value.attrs.values()):
                    forget(item)
                for key in value.attrs:
                    value.attrs[key] = UNKNOWN
                value.attrs[_MISSING] = UNKNOWN
            elif isinstance(value, tuple):
                for item in value:
                    forget(item)
        for value in values:
            forget(value)

    def _method_call(self, owner, name, args, kwargs, path, node):
        arg = self._argument
        if isinstance(owner, (_Table, _OrmTable)):
            if name in {"insert", "update", "delete"}:
                return _Dml(owner)
            if name == "select":
                return _ReadStatement()
        if isinstance(owner, _ReadStatement):
            if name in {"where", "filter", "filter_by", "order_by", "group_by", "limit", "offset", "join", "select_from", "distinct", "having", "execution_options"}:
                return owner
            return UNKNOWN
        if isinstance(owner, _Dml):
            if name in {"values", "returning", "where", "filter", "filter_by", "from_select", "ordered_values", "inline", "execution_options", "prefix_with", "on_conflict_do_update", "on_conflict_do_nothing"}:
                return owner
            return UNKNOWN
        if isinstance(owner, _SqlText):
            return owner if name in {"bindparams", "execution_options"} else UNKNOWN
        if isinstance(owner, _OrmQuery):
            if name in {"filter", "filter_by", "where"}:
                return owner
            if not self.pure and name in {"update", "delete"}:
                self._orm(owner.model, path, node)
            return UNKNOWN
        if isinstance(owner, _SqlFragment):
            if name == "format":
                value = self._format_text(owner.text, args, kwargs, sql=True)
                return _SqlFragment(value) if isinstance(value, str) else UNKNOWN
            if name == "join" and len(args) == 1 and isinstance(args[0], tuple) and all(isinstance(a, _SqlFragment) for a in args[0]):
                return _SqlFragment(self._text(owner.text.join(a.text for a in args[0])))
            return UNKNOWN
        kind = owner.kind if isinstance(owner, _Receiver) else None
        if kind == "engine" and name in {"connect", "begin", "raw_connection"}:
            return _Receiver("connection")
        if kind == "connection" and name == "cursor":
            return _Receiver("cursor")
        if kind == "session_factory" and name == "begin":
            return _Receiver("session")
        if kind == "session" and name == "connection":
            return _Receiver("connection")
        if kind == "session" and name == "query" and len(args) == 1 and not kwargs:
            return _OrmQuery(args[0])
        if kind == "dataframe" and name in {"copy", "assign", "rename", "drop", "astype", "reset_index", "set_index", "fillna", "dropna", "sort_values", "merge", "join", "replace", "query", "filter"}:
            return owner
        if self.pure:
            return UNKNOWN
        if name == "to_sql" and kind in {None, "dataframe"}:
            table = arg(args, kwargs, "name", 0)
            schema = arg(args, kwargs, "schema", 2, None)
            self._write(schema, table, path, node, "to_sql")
        elif name in {"add", "add_all", "bulk_insert_mappings", "bulk_update_mappings", "bulk_save_objects", "delete", "merge"}:
            if kind == "session" or (kind is None and name in {"bulk_insert_mappings", "bulk_update_mappings", "bulk_save_objects"}):
                keyword = "mapper" if name.endswith("_mappings") else "instances" if name in {"add_all", "bulk_save_objects"} else "instance"
                values = arg(args, kwargs, keyword, 0)
                for value in values if isinstance(values, tuple) else (values,):
                    if name.endswith("_mappings") or isinstance(value, _Instance):
                        self._orm(value, path, node)
                    else:
                        self._diagnostic("WRITE_TARGET_UNKNOWN", path, node)
            elif kind is None and args and any(self._class_symbol(value) for value in (args[0] if isinstance(args[0], tuple) else (args[0],))):
                self._diagnostic("WRITE_RECEIVER_UNKNOWN", path, node)
        elif name in {"execute", "executemany", "exec_driver_sql", "copy_expert", "copy"} and kind in {None, "engine", "connection", "cursor", "session"}:
            if args:
                statement = args[0]
            else:
                statement = next((kwargs[key] for key in ("statement", "query", "sql", "operation") if key in kwargs), UNKNOWN)
            if isinstance(statement, _Dml):
                self._orm(statement.model, path, node)
            elif not isinstance(statement, _ReadStatement):
                self._sql(statement, path, node)
        elif name == "copy_from" and kind in {None, "cursor"}:
            table = arg(args, kwargs, "table", 1)
            # psycopg2 copy_from quotes a table name as one identifier in modern
            # versions; historical dotted-name behavior is ambiguous.
            if isinstance(table, str) and "." in table:
                self._diagnostic("WRITE_TARGET_UNKNOWN", path, node)
            else:
                self._write(None, table, path, node, "copy_from")
        return UNKNOWN

    def _sql(self, statement, path, node):
        if isinstance(statement, (_SqlFragment, _SqlText)):
            statement = statement.text
        if not isinstance(statement, str):
            self._diagnostic("WRITE_TARGET_UNKNOWN", path, node)
            return
        targets, incomplete = sql_write_targets(statement)
        for schema, table in targets:
            self._write(schema, table, path, node, "sql")
        if incomplete:
            self._diagnostic("WRITE_TARGET_UNKNOWN", path, node)

    def _orm(self, value, path, node):
        if isinstance(value, _Table):
            self._write(value.schema, value.name, path, node, "orm")
            return
        if isinstance(value, _OrmTable):
            value = value.model
        model = self._class_symbol(value)
        if model is None:
            self._diagnostic("WRITE_TARGET_UNKNOWN", path, node)
            return
        table = self._attr(model, "__table__")
        if isinstance(table, _Table):
            self._write(table.schema, table.name, path, node, "orm")
        elif isinstance(table, _OrmTable):
            self._write(self._orm_schema(model), self._attr(model, "__tablename__"), path, node, "orm")
        else:
            self._diagnostic("WRITE_TARGET_UNKNOWN", path, node)

    def _orm_schema(self, value):
        options = self._class_member(value, "__table_args__")
        if isinstance(options, tuple):
            # SQLAlchemy permits an options dict as the final tuple element.
            if options and isinstance(options[-1], dict):
                options = options[-1]
            elif not options or all(isinstance(item, _Constraint) for item in options):
                options = None
            else:
                options = UNKNOWN
        if isinstance(options, dict):
            schema = options.get("schema")
            if schema is not None:
                return schema
        elif options is not _MISSING and options is not None:
            return UNKNOWN
        metadata = self._class_member(value, "metadata")
        if isinstance(metadata, _Metadata):
            return metadata.schema
        return None if metadata is _MISSING else UNKNOWN

    def _write(self, schema, table, path, node, pattern):
        if (
            not isinstance(table, str)
            or not table
            or _UNKNOWN_TEXT.lower() in table.lower()
            or (schema is not None and (not isinstance(schema, str) or not schema or _UNKNOWN_TEXT.lower() in schema.lower()))
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
            "line": getattr(node, "lineno", 1),
            "pattern": pattern,
        }
        if evidence not in self.result.evidence:
            self.result.evidence.append(evidence)

    def _annotation(self, annotation, path):
        if annotation is None:
            return UNKNOWN
        if isinstance(annotation, ast.Constant) and isinstance(annotation.value, str) and len(annotation.value) < 256:
            try:
                annotation = ast.parse(annotation.value, mode="eval").body
            except SyntaxError:
                return UNKNOWN
        # Type annotations are hints, not executed expressions.
        if not isinstance(annotation, (ast.Name, ast.Attribute)):
            return UNKNOWN
        value = self._expr(annotation, {}, path)
        return self._external_receiver(value.name) if isinstance(value, _External) else UNKNOWN

    def _locals(self, node):
        names = set()
        pending = list(node.body)
        while pending:
            child = pending.pop()
            self._tick()
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                names.add(child.name)
                continue
            if isinstance(child, (ast.Lambda, ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
                continue
            if isinstance(child, ast.Name) and isinstance(child.ctx, (ast.Store, ast.Del)):
                names.add(child.id)
            elif isinstance(child, (ast.Import, ast.ImportFrom)):
                names.update(alias.asname or alias.name.split(".")[0] for alias in child.names if alias.name != "*")
            elif isinstance(child, ast.ExceptHandler) and child.name:
                names.add(child.name)
            elif isinstance(child, (ast.Global, ast.Nonlocal)):
                # The local model cannot safely update module/nonlocal state.
                names.update(child.names)
            pending.extend(ast.iter_child_nodes(child))
        return names

    def _invoke(self, function, args, kwargs, *, entry=False):
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
        env = {name: UNKNOWN for name in self._locals(node)}
        env.update({param.arg: UNKNOWN for param in params + node.args.kwonlyargs})
        defaults = set()
        previous = self.cutoffs.get(symbol.path)
        self.cutoffs[symbol.path] = node.lineno
        self.pure += 1
        try:
            for param, default in zip(params[-len(node.args.defaults):], node.args.defaults):
                env[param.arg] = self._expr(default, {}, symbol.path)
                defaults.add(param.arg)
            for param, default in zip(node.args.kwonlyargs, node.args.kw_defaults):
                if default is not None:
                    env[param.arg] = self._expr(default, {}, symbol.path)
                    defaults.add(param.arg)
        finally:
            self.pure -= 1
            if previous is None:
                self.cutoffs.pop(symbol.path, None)
            else:
                self.cutoffs[symbol.path] = previous
        bound = {param.arg for param, value in zip(params, values)}
        env.update({param.arg: value for param, value in zip(params, values)})
        invalid = len(values) > len(params) and node.args.vararg is None
        if node.args.vararg:
            env[node.args.vararg.arg] = tuple(values[len(params):])
        extras = {}
        keyword_params = {param.arg for param in node.args.args + node.args.kwonlyargs}
        for name, value in kwargs.items():
            if name in keyword_params:
                if name in bound:
                    invalid = True
                env[name] = value
                bound.add(name)
            else:
                extras[name] = value
        if extras and node.args.kwarg is None:
            invalid = True
        if node.args.kwarg:
            env[node.args.kwarg.arg] = extras
        if not entry and any(param.arg not in bound | defaults for param in params + node.args.kwonlyargs):
            invalid = True
        if invalid:
            self._diagnostic("CALL_ARGUMENTS_UNKNOWN", symbol.path, node)
            return UNKNOWN
        for param in params + node.args.kwonlyargs:
            if env[param.arg] is UNKNOWN:
                env[param.arg] = self._annotation(param.annotation, symbol.path)
        # Calls during module/class initialization must see the bindings that
        # exist at that point, not a later reassignment in the source file.
        self.stack.append(symbol)
        try:
            returned, value = self._block(node.body, env, symbol.path)
            if isinstance(function, _Bound) and isinstance(function.receiver, _Instance) and params:
                receiver = env.get(params[0].arg)
                if isinstance(receiver, _Instance) and receiver is not function.receiver:
                    function.receiver.attrs.clear()
                    function.receiver.attrs.update(receiver.attrs)
            return (value if value is not _BREAK and value is not _CONTINUE else UNKNOWN) if returned else None
        finally:
            self.stack.pop()

    def _track_origin(self, value, origin, seen=None):
        seen = set() if seen is None else seen
        if id(value) in seen or not isinstance(value, (dict, tuple, _Instance)):
            return
        seen.add(id(value))
        self._tick()
        if isinstance(value, (dict, _Instance)):
            _, origins = self.mutable_origins.setdefault(id(value), (value, set()))
            origins.add(origin)
        children = value.values() if isinstance(value, dict) else value.attrs.values() if isinstance(value, _Instance) else value
        for child in children:
            self._track_origin(child, origin, seen)

    def _mark_mutated(self, value):
        if self.pure:
            return
        entry = self.mutable_origins.get(id(value))
        if entry:
            for kind, owner, name in entry[1]:
                if kind == "module":
                    self.invalidated_globals.add((owner, name))
                else:
                    self.invalidated_members.add((owner, name))

    @staticmethod
    def _invalidate_dict(value):
        for key in value:
            value[key] = UNKNOWN
        value[_MISSING] = UNKNOWN

    def _assign(self, target, value, env, path):
        if isinstance(target, ast.Name):
            env[target.id] = value
        elif isinstance(target, (ast.Tuple, ast.List)):
            values = value if isinstance(value, (tuple, list)) else ()
            stars = [index for index, item in enumerate(target.elts) if isinstance(item, ast.Starred)]
            if not stars and len(values) == len(target.elts):
                for item, part in zip(target.elts, values):
                    self._assign(item, part, env, path)
            elif len(stars) == 1 and len(values) >= len(target.elts) - 1:
                index = stars[0]
                tail = len(target.elts) - index - 1
                parts = (*values[:index], tuple(values[index:len(values)-tail]), *values[len(values)-tail:])
                for item, part in zip(target.elts, parts):
                    self._assign(item.value if isinstance(item, ast.Starred) else item, part, env, path)
            else:
                for name in self._target_names(target):
                    env[name] = UNKNOWN
        elif isinstance(target, ast.Attribute):
            owner = self._expr(target.value, env, path)
            if isinstance(owner, _Instance):
                self._mark_mutated(owner)
                if len(owner.attrs) >= MAX_ITEMS and target.attr not in owner.attrs:
                    raise _Limit()
                owner.attrs[target.attr] = value
            elif isinstance(owner, _Symbol):
                # Runtime class/module assignment may change the identity on
                # every subsequent access. Never resurrect its source default.
                if not self.pure:
                    if owner.name:
                        self.invalidated_members.add((owner, target.attr))
                    else:
                        self.invalidated_globals.add((owner.path, target.attr))
                self._diagnostic("STATEMENT_UNSUPPORTED", path, target)
        elif isinstance(target, ast.Subscript):
            owner = self._expr(target.value, env, path)
            key = self._expr(target.slice, env, path)
            if isinstance(owner, dict):
                self._mark_mutated(owner)
                if len(owner) >= MAX_ITEMS and (not isinstance(key, (str, int)) or key not in owner):
                    raise _Limit()
                if isinstance(key, (str, int)):
                    owner[key] = value
                else:
                    self._invalidate_dict(owner)

    @staticmethod
    def _known_truth(value):
        """Only literal values have a safe Python truth value in this domain."""
        return type(value) in (bool, int, str, tuple, dict, type(None)) and (
            not isinstance(value, str) or _UNKNOWN_TEXT.lower() not in value.lower()
        )

    def _fork(self, env):
        # Copy nested mutable abstract values while preserving sentinel identity.
        memo = {}

        def clone(value):
            if isinstance(value, dict):
                if id(value) not in memo:
                    memo[id(value)] = {}
                    memo[id(value)].update({key: clone(item) for key, item in value.items()})
                    if id(value) in self.mutable_origins:
                        self.mutable_origins[id(memo[id(value)])] = (memo[id(value)], set(self.mutable_origins[id(value)][1]))
                return memo[id(value)]
            if isinstance(value, _Instance):
                if id(value) not in memo:
                    memo[id(value)] = _Instance(value.model)
                    memo[id(value)].attrs.update({key: clone(item) for key, item in value.attrs.items()})
                    if id(value) in self.mutable_origins:
                        self.mutable_origins[id(memo[id(value)])] = (memo[id(value)], set(self.mutable_origins[id(value)][1]))
                return memo[id(value)]
            if isinstance(value, tuple):
                return tuple(clone(item) for item in value)
            return value

        return {key: clone(value) for key, value in env.items()}

    @staticmethod
    def _merge(env, branches):
        keys = set().union(*(branch.keys() for branch in branches))
        for key in keys:
            values = [branch.get(key, UNKNOWN) for branch in branches]
            if all(isinstance(value, _Instance) for value in values) and all(value.model == values[0].model for value in values):
                attrs = {}
                for name in set().union(*(value.attrs.keys() for value in values)):
                    members = [value.attrs.get(name, UNKNOWN) for value in values]
                    attrs[name] = members[0] if all(member == members[0] for member in members) else UNKNOWN
                env[key] = _Instance(values[0].model, attrs)
            else:
                env[key] = values[0] if all(value == values[0] for value in values) else UNKNOWN

    def _forget_mutations(self, env, statements, path):
        """Discard facts that may be invalidated by an unmodeled execution path."""
        pending = list(statements)
        has_call = False
        while pending:
            node = pending.pop()
            self._tick()
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                env[node.name] = UNKNOWN
                continue
            if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
                env[node.id] = UNKNOWN
            elif isinstance(node, (ast.Attribute, ast.Subscript)) and isinstance(node.ctx, (ast.Store, ast.Del)):
                root = node.value
                while isinstance(root, (ast.Attribute, ast.Subscript)):
                    root = root.value
                if isinstance(root, ast.Name):
                    env[root.id] = UNKNOWN
            elif isinstance(node, ast.Call):
                has_call = True
            elif isinstance(node, ast.MatchAs) and node.name:
                env[node.name] = UNKNOWN
            elif isinstance(node, ast.MatchStar) and node.name:
                env[node.name] = UNKNOWN
            elif isinstance(node, ast.MatchMapping) and node.rest:
                env[node.rest] = UNKNOWN
            pending.extend(ast.iter_child_nodes(node))
        if has_call:
            # Unknown calls may mutate aliased mutable values; literals and
            # source symbols remain useful when no assignment changed them.
            for key, value in env.items():
                if isinstance(value, (dict, _Instance, tuple)):
                    env[key] = UNKNOWN

    def _block(self, statements, env, path):
        for node in statements:
            self._tick()
            if isinstance(node, (ast.Assign, ast.AnnAssign)):
                value = self._expr(node.value, env, path)
                for target in node.targets if isinstance(node, ast.Assign) else [node.target]:
                    self._assign(target, value, env, path)
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                for name, binding in self._imports_for(node, path, self._module(path)).items():
                    env[name] = self._value(binding) if isinstance(binding, _Symbol) else binding
            elif isinstance(node, ast.AugAssign):
                value = self._expr(ast.BinOp(left=node.target, op=node.op, right=node.value), env, path)
                self._assign(node.target, value, env, path)
            elif isinstance(node, (ast.Global, ast.Nonlocal)):
                self._diagnostic("STATEMENT_UNSUPPORTED", path, node)
                return True, UNKNOWN
            elif isinstance(node, ast.Expr):
                if not isinstance(node.value, ast.Constant):
                    self._expr(node.value, env, path)
            elif isinstance(node, ast.Return):
                return True, self._expr(node.value, env, path)
            elif isinstance(node, ast.Break):
                return True, _BREAK
            elif isinstance(node, ast.Continue):
                return True, _CONTINUE
            elif isinstance(node, (ast.For, ast.AsyncFor)):
                values = self._expr(node.iter, env, path)
                if isinstance(values, dict):
                    values = tuple(values)
                if not isinstance(values, (tuple, list)):
                    # The loop can be empty or execute an arbitrary number of
                    # times. Keep its evidence, but do not guess post-loop state.
                    self._diagnostic("DYNAMIC_LOOP", path, node)
                    branch = self._fork(env)
                    self._assign(node.target, UNKNOWN, branch, path)
                    self._block(node.body, branch, path)
                    self._forget_mutations(env, [node.target, *node.body, *node.orelse], path)
                    self._block(node.orelse, self._fork(env), path)
                    continue
                if len(values) > MAX_ITEMS:
                    raise _Limit()
                for value in values:
                    self.iterations += 1
                    if self.iterations > MAX_ITERATIONS:
                        raise _Limit()
                    self._assign(node.target, value, env, path)
                    stopped, result = self._block(node.body, env, path)
                    if stopped:
                        if result is _BREAK:
                            break
                        if result is _CONTINUE:
                            continue
                        return stopped, result
                else:
                    stopped, result = self._block(node.orelse, env, path)
                    if stopped:
                        return stopped, result
            elif isinstance(node, ast.If):
                test = self._expr(node.test, env, path)
                if self._known_truth(test):
                    returned, value = self._block(node.body if test else node.orelse, env, path)
                    if returned:
                        return returned, value
                else:
                    branches = []
                    exits = []
                    for branch in (node.body, node.orelse):
                        branch_env = self._fork(env)
                        stopped, value = self._block(branch, branch_env, path)
                        if stopped:
                            exits.append(value)
                        else:
                            branches.append(branch_env)
                    if not branches:
                        if exits[0] is exits[1] or exits[0] == exits[1]:
                            return True, exits[0]
                        self._diagnostic("CONTROL_FLOW_UNKNOWN", path, node)
                        return True, UNKNOWN
                    self._merge(env, branches)
                    if exits:
                        self._diagnostic("CONTROL_FLOW_UNKNOWN", path, node)
            elif isinstance(node, (ast.With, ast.AsyncWith)):
                for item in node.items:
                    value = self._expr(item.context_expr, env, path)
                    if item.optional_vars is not None:
                        # Known SQLAlchemy/driver sessions, connections and cursors
                        # return themselves from their context manager. Do not
                        # assume arbitrary managers implement that protocol.
                        entered = value if isinstance(value, _Receiver) and value.kind in {"session", "connection", "cursor"} else UNKNOWN
                        self._assign(item.optional_vars, entered, env, path)
                returned, value = self._block(node.body, env, path)
                if returned:
                    return returned, value
            elif isinstance(node, ast.Try):
                # Exception flow is not modeled precisely. Do not promote
                # values from the normal path into exception/finally paths.
                normal = self._fork(env)
                stopped, value = self._block(node.body, normal, path)
                if not stopped:
                    stopped, value = self._block(node.orelse, normal, path)
                branches = [] if stopped else [normal]
                exits = [value] if stopped else []
                for handler in node.handlers:
                    branch = {key: UNKNOWN for key in env.keys() | normal.keys()}
                    if handler.name:
                        branch[handler.name] = UNKNOWN
                    handler_stop, handler_value = self._block(handler.body, branch, path)
                    if handler_stop:
                        exits.append(handler_value)
                    else:
                        branches.append(branch)
                if node.handlers:
                    self._diagnostic("CONTROL_FLOW_UNKNOWN", path, node)
                if node.finalbody:
                    final_env = self._fork(normal) if not node.handlers else {
                        key: UNKNOWN for key in env.keys() | normal.keys()
                    }
                    final_stop, final_value = self._block(node.finalbody, final_env, path)
                    if final_stop:
                        return final_stop, final_value
                    if branches:
                        self._merge(env, [final_env])
                elif branches:
                    self._merge(env, branches)
                if not branches:
                    return True, exits[0] if all(v == exits[0] for v in exits) else UNKNOWN
            elif isinstance(node, ast.While):
                while True:
                    test = self._expr(node.test, env, path)
                    if not self._known_truth(test):
                        self._diagnostic("DYNAMIC_LOOP", path, node)
                        branch = self._fork(env)
                        self._block(node.body, branch, path)
                        # A dynamic loop may execute zero or many times. The
                        # else path is reachable unless it leaves via break.
                        self._forget_mutations(env, node.body, path)
                        self._block(node.orelse, self._fork(env), path)
                        self._forget_mutations(env, node.orelse, path)
                        break
                    if not test:
                        stopped, value = self._block(node.orelse, env, path)
                        if stopped:
                            return stopped, value
                        break
                    self.iterations += 1
                    if self.iterations > MAX_ITERATIONS:
                        raise _Limit()
                    stopped, value = self._block(node.body, env, path)
                    if stopped and value is _BREAK:
                        break
                    if stopped and value is not _CONTINUE:
                        return stopped, value
            elif isinstance(node, ast.Assert):
                test = self._expr(node.test, env, path)
                if self._known_truth(test) and not test:
                    return True, UNKNOWN
                if not self._known_truth(test):
                    self._diagnostic("CONTROL_FLOW_UNKNOWN", path, node)
            elif isinstance(node, ast.Delete):
                for target in node.targets:
                    self._assign(target, UNKNOWN, env, path)
            elif isinstance(node, ast.Raise):
                self._expr(node.exc, env, path)
                self._diagnostic("CONTROL_FLOW_UNKNOWN", path, node)
                return True, UNKNOWN
            elif not isinstance(node, (ast.Pass, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                self._diagnostic("STATEMENT_UNSUPPORTED", path, node)
                self._forget_mutations(env, [node], path)
        return False, UNKNOWN
