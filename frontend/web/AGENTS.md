# AGENTS.md — frontend web router

## 1. Scope

This file applies to:

```text
frontend/web/**
```

Use it together with:

- root [`AGENTS.md`](../../AGENTS.md);
- repository rules [`rules/README.md`](../../rules/README.md);
- applicable workflows under [`rules/workflows/`](../../rules/workflows/);
- current behavioral specs under `openspec/specs/**` resolved through repository policy.

This file defines frontend-specific routing, architecture conventions, and verified operational constraints.

It does **not** define backend business/calculation semantics.

If this file conflicts with root invariants or canonical routing, classify it as `BROKEN_ROUTING` and stop semantic editing until the conflict is resolved.

---

## 2. Frontend responsibilities

`frontend/web/` owns:

- entity-management UI;
- reporting UI;
- charts and visualizations;
- calculation start/stop controls;
- user interaction and presentation;
- frontend application state;
- consumption of backend contracts.

Frontend code may adapt data for presentation, but must not invent a second interpretation of backend business semantics.

---

## 3. Technical stack

Current stack:

- React 18+ with TypeScript;
- Vite;
- Zustand;
- `@tanstack/react-query`;
- React Router;
- Ant Design;
- AG Grid Community;
- Plotly.js;
- MSW.

Before introducing a new runtime dependency, justify why existing project abstractions are insufficient.

---

## 4. Project structure

Primary areas:

```text
src/app/
  concrete application metadata, auth/permission adapters, app-owned core/store/API,
  HomePage and Vite module discovery/router bootstrap

src/modules/
  self-contained feature modules auto-discovered via
  import.meta.glob('/src/modules/*/index.tsx')
  (portal: assistant, catalog, documents, admin); each exports ModuleRegistration

src/shared/
  reusable UI, hooks, utilities, generated/shared API consumers

src/mocks/
  MSW handlers and mock data

scripts/generate-api.ts
  API generation implementation
```

Shared frontend foundation now lives outside `web`:

```text
frontend/ui-kit/
  generic presentation/theme/controls

frontend/app-shell/
  application bootstrap/providers, main layout, sidebar/navigation,
  auth/permission presentation, router composition and plugin runtime
```

Dependency direction is `web -> app-shell -> ui-kit`. Business/domain code and generated API remain in `web`; `app-shell` must not import them. `app-shell` must also remain independent of the concrete application state manager (`Zustand`/`RootState`) and application permission implementation (`Action`, `canPerform`, role/resource policy). Application adapters under `web/src/app/adapters/**` translate those concrete implementations to shell-owned auth/permission contracts. Plugin metadata contracts (`MenuItem`, `ModuleRegistration`) should be imported directly from `@asset-management/app-shell/plugin`; do not recreate compatibility copies in `web`.

Module-local conventions should preserve clear feature boundaries.

Typical module structure:

```text
index.tsx
menu.tsx
components/
pages/
store/
styles/
```

`store/` contains Zustand slice/state logic for the module.

Do not introduce a parallel state-management architecture without explicit architectural scope.

---

## 5. Scoped routing

| Changed scope | Additional routing |
|---|---|
| API consumer/generated API surface | `SPEC-WF-API-CONTRACT` |
| `scripts/generate-api.ts` | API generation workflow + `AMB-005` command/path verification |
| `src/app/core/api/client.ts` | API client infrastructure; inspect consumer-wide impact |
| `src/app/core/api/interceptors.ts` | API transport infrastructure; inspect auth/error/compatibility impact |
| `src/app/core/store/**` | Global state architecture; inspect cross-module impact |
| `src/app/core/auth/**` | Authentication/permissions; treat as security-sensitive |
| valuation/filter UI | Resolve valuation/filter topic; semantic reinterpretation is high-risk |
| visualization/dashboard logic | Resolve applicable backend semantic topic if date/calculation interpretation changes |
| presentation-only UI | May remain `autonomous` if no stricter topic/boundary policy applies |

A sensitive path increases required scrutiny; it does not automatically prove a semantic change.

---

## 6. API contract and generated client rules

Public HTTP API changes follow:

[`SPEC-WF-API-CONTRACT`](../../rules/workflows/api-contract.md).

Contract chain:

```text
FastAPI routes/models
-> published OpenAPI
-> generated TypeScript API client/types
-> frontend consumers
```

### Non-overridable API rules

- Never hand-edit generated API files.
- Never create handwritten request/response models when the generated backend contract already defines them.
- Never add a new direct HTTP workaround such as:
  - `fetch('/api/...')`;
  - raw `apiClient.get('/path/...')`;
  - equivalent ad-hoc endpoint calls;
  when the endpoint belongs to the registered generated API boundary.
- Do not bypass code generation because generation is inconvenient or temporarily unavailable.
- If generation is unavailable, record a blocker rather than implement a parallel client.
- Do not change frontend request/response shape independently from backend contracts.

### API client customization

Transport-wide customization belongs in stable wrapper/infrastructure points such as:

```text
src/app/core/api/client.ts
src/app/core/api/interceptors.ts
```

Do not customize generated files directly.

### New backend method

Required sequence:

```text
backend FastAPI source
-> backend verification
-> OpenAPI export
-> inspect OpenAPI diff
-> regenerate frontend API
-> use generated function/types
-> verify frontend consumer
```

After OpenAPI/generated paths appear, rerun `ApplicableContext`.

---

## 7. Canonical API generation

The frontend API generator is now verified.

Canonical package command:

```bash
cd frontend/web && npm run gen-api
```

`package.json` maps it to:

```text
tsx scripts/generate-api.ts
```

Generator implementation:

```text
frontend/web/scripts/generate-api.ts
```

Input:

```text
common/contracts/openapi/openapi.json
```

Output:

```text
frontend/web/src/shared/api/generated
```

Therefore:

- `npm run gen-api` is the canonical frontend API generation command;
- `npm run generate-api` is not a valid repository command;
- generated output under `src/shared/api/generated/` is read-only;
- `AMB-005` is resolved for API generation command/output.

The current manifest does **not** define `lint` or `test` scripts. Do not make `npm run lint` or `npm test` mandatory unless the manifest changes and the registry is updated.

---

## 8. JSON Schema / generated forms

Where the frontend uses repository JSON Schema contracts:

```text
common/contracts/jsonschema/
```

the frontend should consume generated schema artifacts rather than manually recreate backend model semantics.

If a required schema is missing:

1. resolve the backend authoring model;
2. use the registered JSON Schema generation pipeline;
3. regenerate the published schema;
4. consume the generated schema from frontend.

Do not invent a frontend-only schema for an existing backend model as a workaround.

For complex forms, prefer the project declarative form approach when compatible with the current feature architecture.

---

## 9. Zustand state architecture

### Store shape

The application uses a flat Zustand store.

Slices are merged at the root level through the project initializer/registration mechanism.

Do not reintroduce nested legacy access patterns.

### Slice typing

Prefer slice-local typing, e.g.:

```typescript
StateCreator<MySliceState, [], [], MySliceState>
```

rather than typing a slice as the entire root store.

### Registration

The shell plugin registry is state-manager agnostic. Module Zustand slices are registered through the web-owned plugin-contribution adapter (`src/app/core/store/pluginContributions.ts`) from the module entry point. Do not add Zustand types or store-shape knowledge to `app-shell`.

### Placement

Module-local Zustand state belongs under that module's:

```text
store/
```

Shared/global state belongs under the established application-core store area.

### Naming

Because the root store is flat, state/action names must be unique enough to avoid collisions.

Avoid generic cross-module names such as:

```text
filters
list
loading
```

when another module may define the same root key.

Prefer domain/page-prefixed names such as:

```text
monitoringFilters
indexDailyFilters
simulationFilters
dashboardFilters
```

### Updates

Prefer direct flat updates:

```typescript
set({ field: value })
```

Do not recreate the obsolete nested-slice pattern.

Use `get()` for current state access inside actions when required.

### Sensitive data

Do not store credentials/tokens in arbitrary feature slices. Use the established auth mechanisms.

### Async state

Async actions must model relevant loading/error state explicitly.

For server-state fetching/caching, prefer the established `@tanstack/react-query` patterns where appropriate rather than duplicating server cache in Zustand without reason.

---

## 10. UI component rules

- Reusable UI belongs under `src/shared/ui/` or the established shared UI location.
- Shared components such as tables/form builders must not contain business logic for one feature.
- Feature-specific behavior belongs in the feature/module layer.
- Plotly/visualization components must handle:
  - empty state;
  - loading state;
  - partial/missing data;
  - resize/container changes.

For large datasets, avoid heavy synchronous work on the main thread. Prefer backend processing or an appropriate worker strategy when justified.

---

## 11. Data/filter semantic boundary

Frontend must not independently redefine backend filter semantics.

Rules:

- If backend returns already-filtered data, do not silently apply another business filter.
- UI-only/user-selected filtering is allowed when it is explicitly presentation behavior rather than reinterpretation of backend rules.
- When backend filter semantics change, inspect all affected controls/labels/forms/consumers.
- Nullable fields must render safely without becoming an implicit semantic fallback.
- Empty/missing/default values must not be reinterpreted into a new business value on frontend.

If frontend behavior would alter valuation/filter/date/calculation semantics:

```text
resolve governing topic
+
SPEC-WF-HIGH-RISK-SEMANTICS
+
approval_policy: human_required
```

---

## 12. Module interaction rules

- Feature modules should not import each other's internal implementation directly.
- For shared concerns prefer:
  - shared utilities/components;
  - shared application state where appropriate;
  - events;
  - backend/API queries through the shared/generated boundary.
- Shared types/utilities belong in `src/shared/` or another established shared layer.
- Do not copy the same transport/business model into multiple feature modules.

---

## 13. Visualization and dashboards

Sensitivity controls and calculation-oriented UI must remain aligned with governing backend semantics.

Do not locally reinterpret:

- calculation presets;
- sensitivity ranges;
- dates;
- periods;
- intervals;
- missing/stale curve values;
- result meaning.

Presentation transformations are allowed; semantic transformations require governing topic/workflow resolution.

Graphs must handle missing/partial datasets safely.

---

## 14. React / TypeScript conventions

- Prefer functional components and hooks.
- Use TypeScript strict-mode-compatible code.
- Avoid `any`; when unavoidable, constrain it locally and document the reason.
- Use `useCallback`/memoization when there is an actual referential-stability or performance need, not by default.
- Keep component boundaries clear.
- Avoid excessive prop drilling; use existing state/context/query abstractions where they clarify ownership.
- Do not move CPU-heavy processing onto the main thread when backend/worker processing is more appropriate.

---

## 15. Testing and verification expectations

Where supported by the repository test setup, add targeted evidence for behavior changes.

Examples:

- form validation/error states;
- API consumer request/response handling;
- empty/partial/full visualization datasets;
- filter/display regressions;
- nullable/error states.

Do not invent test commands that are not present in the current repository manifest.

### Confirmed build command

```bash
cd frontend/web && npm run build
```

### API generation

```bash
cd frontend/web && npm run gen-api
```

### Lint/test commands

The current `package.json` does not define `lint` or `test` scripts.

Do not run or require:

```text
npm run lint
npm test
```

unless those scripts are added later and repository routing/verification metadata is updated.

---


### Verification command source

Use concrete invocations registered in `rules/policy.yaml`.

Do not invent package scripts or rewrite registered commands.
Current verified frontend scripts are `gen-api` and `build`; `lint`, `test`, and
`generate-api` are not present in the current manifest.


## 16. Approval policy

### Presentation-only UI

May resolve to:

```text
autonomous
```

when:

- no public contract changes;
- no backend/business semantics change;
- no security/auth semantics change;
- no stricter applicable topic/workflow policy applies.

### Consumer-contract change

Follow `SPEC-WF-API-CONTRACT`.

### Business-semantic reinterpretation

Minimum:

```text
human_required
```

with `SPEC-WF-HIGH-RISK-SEMANTICS`.

The strictest applicable policy wins.

---

## 17. Closeout

In addition to root closeout, record:

- frontend scopes changed;
- presentation-only vs consumer-contract vs semantic classification;
- resolved `approval_policy`;
- API/schema workflows applied;
- generated artifacts affected;
- whether generated files were regenerated rather than edited;
- frontend consumer impact;
- build/generation commands actually executed;
- unavailable checks omitted because the current manifest does not define them;
- affected nullable/filter/date/calculation assumptions;
- unresolved blockers or evidence gaps.

Do not close API consumer work while generated contract reconciliation or required upstream approval remains unresolved.

---

## 18. Portability

This router must remain usable in Cursor, ZooCode, and future agent environments.

Tool-specific configuration may not:

- contain the only copy of frontend/backend semantic rules;
- relax repository approval policy;
- bypass generated API/schema contracts;
- hide required contract evidence.

Repository routing remains canonical.
