# Frontend architectural boundaries

This is implementation guidance and verification evidence, not a new behavioral contract.
The [catalog specification](../openspec/specs/catalog/spec.md) remains authoritative.

## Ownership and composition

- The host application composes services, the application cache, authentication,
  permissions, module discovery, and the intentionally catalog-backed home page.
- The reusable shell owns generic composition, navigation, providers, and page
  boundaries. It must not import generated API, Zustand, or business permission policy.
- Features own server-state queries and presentation; the UI kit owns generic UI.
- [The catalog entry](web/src/modules/catalog/index.tsx) exposes the public home
  component. [The host home](web/src/app/home/HomePage.tsx) does not import a feature page internally.

All four current modules are explicitly required by [the host router](web/src/app/router/index.tsx).
An import failure, missing/disabled required module, invalid registration, or duplicate
module identity fails startup rather than silently omitting a feature. Imports run in
parallel; registration order remains deterministic. Disabled non-required modules are
the only intentional skip mechanism; no current module is implicitly optional.

[The registry](app-shell/src/plugin/registry.ts) stages the entire registration batch
before publication. It rejects duplicate module IDs, explicit route IDs, normalized
route patterns, recursive menu paths, and contribution slot/key pairs. A failed batch
does not publish partial menus or contributions. These checks are runtime boundaries,
not an independently executed test suite. They do not detect every possible router
overlap or roll back external import/callback side effects. Registration callbacks
must be synchronous and must not mutate external state.

[Lazy page boundaries](app-shell/src/routing/RouteSuspense.tsx) isolate import/render
failures, reset on navigation, and provide a reload action. [Startup handling](web/src/main.tsx)
shows a failure message without rendering a partially composed application.

## Generated transport and service scope

[The generator authoring source](web/scripts/generate-api.ts) explicitly selects the
installed generator's legacy Fetch transport. The old plugin setting belonged to a
different configuration API and was silently falling back to Fetch. Generation now
also reports failures through a nonzero process exit status. Existing generated
operation names, response bodies, types, and cancellable request signatures are retained.

[Published OpenAPI](../common/contracts/openapi/openapi.json) feeds
[generated output](web/src/shared/api/generated/index.ts). Never edit that output by
hand or add handwritten endpoint/model substitutes. Backend authoring sources and the
published contract were not changed by this hardening work. The registered generator
was rerun against the current published source; no backend export was needed.

[Host API infrastructure](web/src/app/core/api/client.ts) configures the actual generated
Portal transport once, before session bootstrap, using the existing Portal base URL,
cookie credentials, and API-key provider. The key is applied after generated headers,
including the session operation's optional header.

The configured API root may already end in the API segment. Generated Portal calls
remove that final segment and trailing slashes from their base because generated
operation paths already contain it. This preserves a deployment prefix and avoids
duplicating the API segment. The legacy Axios base retains its existing API-root
meaning; independent service configurations are not normalized using Portal rules.
Authentication endpoint failures
remain caller-owned; protected Portal 401 responses expire local auth/cache without
recursively calling the logout endpoint. The legacy Axios blob utility remains separate
and rejects cross-origin overrides before adding Portal credentials. New API operations
must use generated services, not that utility.

The same infrastructure exposes independent, frozen service configurations with their
own interceptor collections. Defaults omit credentials, attach no Portal key, and
install no global logout handler. The host must explicitly choose a credential provider
and failure policy for each approved service. Never change the generated Portal base
URL per request or reuse its configuration for another backend. The current generated
function surface is Portal-scoped; this foundation is not a claim that a secondary
service SDK or contract already exists.

## Server data and authentication lifetime

[Catalog queries](web/src/modules/catalog/queries.ts) own typed keys namespaced by
Portal service and catalog feature, including asset, roots, filters, periods, and
pagination. Overview, storage, changes, object detail, lineage, Universe, loads, and
the objects list consume these hooks. Requests connect React Query cancellation to
the generated transport and remove abort listeners after settlement.

No previous-data placeholder carries one asset's graph into a different selection.
Graph instances are keyed by selection. Loading, failures, successful emptiness, and
confirmed load unavailability remain distinct. Independent requests expose independent
failures. Snapshot freshness comes from response collector metadata, not a client-side
freshness timestamp. Roots still use the roots operation; selected assets use bounded
lineage traversal. Nullable values and unresolved targets retain their API meaning.

[One host-owned query client](web/src/app/core/queryClient.ts) is passed to shell
providers. All current application query data is treated as private. Login/logout
transitions, account/auth-type/permission changes, and protected Portal authentication
expiry cancel and remove query data. Mutation cache entries are also removed; this
does not undo an already submitted server mutation. Shell auth adapters remain generic.
Future public-cache exceptions would require an explicit lifecycle policy, not an
assumption that a second backend needs a second query client.

## Flat client state

[The store initializer](web/src/app/core/store/initializer.ts) retains the mandated
flat store and validates every core/feature root key before publishing it. Duplicate
keys fail with ownership context rather than overwriting previous state.
[Root types](web/src/app/core/store/types.ts) no longer have an unrestricted index
signature. Future features declare their flat state through interface augmentation
and use [the typed contribution adapter](web/src/app/core/store/pluginContributions.ts).
The shell remains state-manager agnostic.

Auth, permissions, and existing client-state selectors remain available. No feature
currently registers a slice. The obsolete persisted selected-contract key had no
authoring slice or consumers; its persistence/hydration was removed, without deleting
existing browser storage. Existing theme/notification selectors were retained rather
than expanding this change into public-state cleanup. Backend data belongs in Query,
not additional Zustand server caches.

## Future services remain blocked on contracts

Current catalog, storage, lineage, changes, and load-history reads continue through
Portal API as required by [the current catalog contract](../openspec/specs/catalog/spec.md:233).
There is no approved separate lineage read contract. Moving these reads to another
backend requires an approved behavioral/compatibility decision and registered contract
generation/reconciliation; service configuration alone does not authorize that move.

[Document upload](web/src/modules/documents/pages/DocumentUploadPage.tsx) remains a
placeholder. No upload endpoint, fake request, or simulated successful upload was added.
A future service requires approved operation/request/response/error/cancellation rules,
credential and authorization scope, and host configuration/deployment decisions before
an upload consumer can be implemented. None of those choices is inferred here.

## Verification and limitations

Canonical invocations are registered in [repository policy](../rules/policy.yaml:188):

```sh
cd frontend/web && npm run gen-api
cd frontend/web && npm run build
```

Generation succeeded against the current published OpenAPI and emitted Fetch output.
The first build caught a header-resolver typing issue; it was corrected. Subsequent
builds completed TypeScript compilation and production bundling. The final build after
the initial hardening code changes exited successfully, transformed 5,879 modules, and bundled in 10.42
seconds. Build warnings noted large chunks and the catalog entry's deliberate static
Home import alongside discovery. Both registered generation runs also exited successfully.

A subsequent login report exposed a duplicated API segment when the configured API
root was passed directly to generated operations. The Portal-specific base correction
described above passed the same registered build: 5,879 modules, exit status zero,
bundled in 9.14 seconds, with the same warnings. Live login was not exercised by that build.

No lint, unit-test, browser-test, installation, or unregistered validation command was
run. The web manifest has no lint/test scripts. Build success is not evidence of a live
cross-origin session, visual interaction, cancellation race, or runtime regression test.
No extra verification workflow or governance command was introduced. The API workflow's
legacy contract name was explicitly approved as the current registry name for this
task only; governance files were not rewritten. A VCS baseline diff was not independently
executed under the restricted command scope, so generation success is not a claim that
every generated artifact was already byte-identical before this work.
