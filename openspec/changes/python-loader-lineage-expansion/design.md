# Design

Use a Python-only symbolic AST analyzer; leave legacy Airflow pipelines intact.
Index symbols by source module and class, resolve local imports lazily within
the configured root, and use explicit budgets for source size, module count,
AST size, recursive resolution, calls, expression steps and loop iterations.

Configured classes dispatch through `load_file` (including inherited methods);
configured functions dispatch directly. Without configuration, infer exactly
one loader class or one module-level function; ambiguous modules produce no
guessed target. Class methods retain the selected subclass as receiver, including
`super` dispatch. Local helper signatures bind actual positional/keyword values.

Symbolic values include literals, dictionaries, tuples, module/class/function
references and unknown. Resolve inherited ORM metadata only when a reachable
write uses the model. Traverse finite dictionaries/tuples and propagate values
through assignments, unpacking, helper arguments and return values. Runtime
values stay unknown. No eval, importlib, loader execution or network/database
lookup is permitted.

Writes require reachable `to_sql`, executable DML SQL or recognized ORM insert
operations. Local wrappers are followed through their actual source signature,
not guessed positional layouts. All confirmed targets are retained. Provenance
uses relative file, line and pattern in existing process attributes. Unsupported
or unresolved writes and budget exhaustion produce diagnostics.

Qualified targets match only schema plus name; unqualified targets require a
unique catalog name. Catalog mode never invents missing tables; code mode keeps
unresolved TABLE semantics. No view dependency processing is added.

## Verification and reconciliation

Use registered CORE-PYTEST-TARGET for `tests/unit/test_catalog` and
CORE-PYTEST-UNIT. Tests create independent temporary source trees. Reconcile
the current ingestion spec after implementation; record actual results and any
missing evidence. Approval already covers these semantics; reopen only for new
semantic ambiguity. Reroute before expanding changed scopes.
