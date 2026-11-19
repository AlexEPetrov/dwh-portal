## MODIFIED Requirements

### Requirement: Python module lineage из отдельных корней исходников

The existing `APP_DWH_PYTHON_MODULES_ROOT` string MUST accept any number of
semicolon-separated source roots. Components MUST be trimmed; empty components
MUST be ignored; resolved physical paths, including symlink aliases, MUST be
deduplicated. A single root MUST remain backwards compatible. Unavailable roots
MUST be diagnosed without blocking valid roots; no usable roots MUST mean
`SUCCESS` with `skipped`. Airflow roots and shared behavior MUST remain separate.

Entry modules and absolute dependencies MUST search all configured roots and
MUST reject multiple distinct physical candidates rather than pick the first.
Duplicated regular package prefixes MUST NOT supply silently mixed children.
Relative imports MUST stay anchored to their declaring package and most specific
containing root, with no fallback to other roots. Resolved symlinks MUST remain
inside the lookup root. Ambiguous modules MUST produce `MODULE_AMBIGUOUS` and
MUST NOT supply new writes, values or storage paths. Independently proven writes
MAY remain as partial lineage. Storage graphs/constants MUST be process-local.

Existing provenance attributes MUST use relative POSIX paths with `root_N/`
prefixes for multiple normalized unique usable roots, and unchanged relative
filenames for one root. Absolute source paths MUST NOT enter Portal DB and
PROCESS identity MUST remain unchanged.

#### Scenario: Registry PROCESS получает WRITES_TO из AST модулей

- GIVEN `APP_DWH_PYTHON_MODULES_ROOT` указывает на дерево с модулем `loaders.ice_brent`
- AND registry создал PROCESS с `module=loaders.ice_brent`
- AND в модуле есть свидетельство записи в `raw.ice_brent`
- AND таблица есть в снимке каталога
- WHEN выполняется адаптер `python_modules` в режиме `catalog`
- THEN у того же PROCESS есть ребро `WRITES_TO` на таблицу
- AND новый PROCESS не создаётся

#### Scenario: Корень модулей не задан

- GIVEN `APP_DWH_PYTHON_MODULES_ROOT` пуст
- WHEN выполняется адаптер `python_modules`
- THEN статус прогона `SUCCESS` со `skipped`
- AND рёбра registry PROCESS не меняются этим адаптером

#### Scenario: Модуль в пятом корне и повторные компоненты

- GIVEN five roots with whitespace, empty components and normalized/symlink duplicates
- WHEN the entry module exists only in the fifth unique usable root
- THEN it is found with root-disambiguated relative provenance
- AND repeated paths do not create ambiguity

#### Scenario: Неоднозначные входной модуль или абсолютная зависимость

- GIVEN two distinct files claim the same absolute module name in different roots
- WHEN the adapter resolves an entry or dependency using that name
- THEN it diagnoses ambiguity without selecting a source by order
- AND the ambiguous source supplies no new writes or storage paths

#### Scenario: Уникальная зависимость из другого корня

- GIVEN a unique absolute helper in another root and same-named relative helpers
- WHEN a selected loader follows its imports
- THEN the unique absolute helper is resolved across roots
- AND relative helpers come only from their declaring package/root

## ADDED Requirements

### Requirement: Source-aware Python loader TABLE lineage

The Python adapter MUST preserve registry PROCESS identity and analyze only
the configured entry point and reachable local helpers. A class entry point
MUST dispatch through its inherited `load_file`; a callable entry point MUST
dispatch directly. Without an entry point, exactly one loader class or exactly
one module-level callable MAY be inferred; ambiguity MUST be diagnostic and
MUST NOT select arbitrary sibling loaders.

The analyzer MUST resolve module-scoped aliases, relative/transitive imports,
literal schema dictionaries, tuples and inherited ORM attributes. It MUST
propagate finite known values through assignments, helper signatures and loops
under explicit resource budgets, without importing or executing loader code.
Unknown values and exhausted budgets MUST remain diagnostic rather than guessed.

All independently proven reachable TABLE writes MUST be retained with relative
file/line/pattern evidence. Unused declarations, read-only ORM references,
docstrings and unrelated sibling loaders MUST NOT create write targets.
Qualified references MUST NOT match a same-named table in another schema.
Catalog/code materialization rules MUST remain unchanged. PostgreSQL view
dependencies, Airflow inference and public HTTP shape MUST NOT change.

#### Scenario: Selected subclass writes through inherited helpers

- GIVEN a configured subclass with imported ORM metadata and an inherited writer
- WHEN its reachable helper writes a primary and a secondary table
- THEN both TABLE targets are retained on the same PROCESS
- AND unused sibling loaders and read-only model references are excluded

#### Scenario: Finite configuration loop

- GIVEN a selected loader iterates literal schema/table tuples
- WHEN tuples reach a local wrapper and then `to_sql`
- THEN all proven targets are retained with source evidence
- AND runtime-dependent targets remain diagnostic

#### Scenario: Schema-qualified mismatch

- GIVEN a proven write to `inbox.measurements`
- AND the catalog contains only `other.measurements`
- WHEN matching the write
- THEN catalog mode does not match the other schema
- AND code mode retains an unresolved `inbox.measurements` TABLE
