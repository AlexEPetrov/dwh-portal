# Design

Use a Python-only symbolic AST analyzer; leave legacy Airflow pipelines intact.
Index symbols by source module and class, resolve local imports lazily within
the configured roots, and use explicit budgets for source size, module count,
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

The existing `python_modules_root` string accepts any number of `;`-separated
paths. Trim components, ignore empty ones, resolve paths and deduplicate aliases
before lookup. Diagnose unavailable roots with portable ordinal labels, continue
valid roots, and skip successfully when none remain. Keep Airflow settings and
shared resolvers unchanged.

One Python-only resolver serves entries, imports and code-mode storage closure.
Absolute names search all roots, deduplicate physical candidates and reject
collisions, including duplicated regular package prefixes. Relative imports
anchor to the declaring file and its most specific containing root; no fallback
to another root is allowed. Candidate symlinks must stay inside their lookup root.
Blocked imports remain unknown, not external name-based writer guesses. Keep
independently proven writes and diagnose partial results.

Preserve process identity. For multiple usable roots, prefix existing relative
POSIX provenance with `root_N/`, ordered by normalized unique usable roots; one
root retains its old relative filenames. Never persist absolute source roots.
The storage graph and constant cache are per process and use these same import
bindings, preventing ambiguity or previous-process state from leaking into it.

Use registered CORE-PYTEST-TARGET for `tests/unit/test_catalog` and
CORE-PYTEST-UNIT. Tests create independent temporary source trees. Reconcile
the current ingestion spec after implementation; record actual results and any
missing evidence. Approval already covers these semantics; reopen only for new
semantic ambiguity. Reroute before expanding changed scopes.
