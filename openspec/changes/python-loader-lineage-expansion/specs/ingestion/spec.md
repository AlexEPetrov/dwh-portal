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
