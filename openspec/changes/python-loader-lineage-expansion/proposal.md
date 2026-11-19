# Python loader lineage expansion

## Scope and approval

Extend the declared `ingestion` capability using its current Python-module
lineage requirement as baseline. This is an approved business-semantic change
(`human_required`): the user explicitly approved entry-point anchored, bounded,
source-aware Python analysis and reconciliation of the current spec.

The user additionally explicitly approved semicolon-separated roots in the
existing string setting, trimming, empty-component removal, physical-path
deduplication, single-root compatibility, and ambiguity-safe lookup for entry
modules and absolute dependencies. Relative imports stay in their declaring
package/root. Extend this same approved ingestion change; no new capability,
HTTP surface or generated contract is introduced.

Authoring scopes: registry collector, Python lineage adapter and a dedicated
static analyzer, independent catalog unit tests, and OpenSpec artifacts.
Preserve process identity; retain only the safe entry-point identifier, not
handler options. The sample source directory is read-only and not a test fixture.

## Non-goals and contracts

Stop at PostgreSQL TABLE targets. Do not change PostgreSQL/view dependencies,
dependent materialized views, shared Airflow inference, frontend, HTTP shape,
OpenAPI or generated artifacts. Catalog and ingestion routing apply. The API
contract workflow has no regeneration edges activated because API authoring
sources and public shape are unchanged. No Python/Rust boundary is affected.

## Outcome

Resolve selected loader classes/callables, local helpers, inherited methods,
module-scoped aliases and finite configuration values without importing or
executing source code. Collect all proven reachable writes and reject schema
fallback across schemas. Unknown values, ambiguity and limits remain diagnostic.
