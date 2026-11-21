# UI Kit extraction report

## Packaging follow-up — 2026-11-21

This report's original Stage-1 source-package/build limitations below are
historical. The package now exports generated ESM, declarations and CSS from
`dist/`. See [current build and delivery instructions](../README.md).
The extraction did not change component behavior or public import subpaths.

## Scope

Source: `frontend/web`

Target: `frontend/ui-kit`

Priority: preserve behavior and avoid refactors with meaningful regression risk.

## Moved to UI Kit

| Previous path | New path | Notes |
|---|---|---|
| `web/src/shared/ui/DataGrid/DataGrid.tsx` | `ui-kit/src/data-grid/DataGrid.tsx` | Implementation moved byte-for-byte. |
| `web/src/shared/ui/DataGrid/AutosumStatusBar.tsx` | `ui-kit/src/data-grid/AutosumStatusBar.tsx` | Implementation moved byte-for-byte. |
| `web/src/shared/ui/MultiSelectFilter.ts` | `ui-kit/src/data-grid/MultiSelectFilter.ts` | Implementation moved byte-for-byte. |
| `web/src/shared/ui/JsonSchemaForm/layout.tsx` | `ui-kit/src/json-schema/layout.tsx` | Implementation moved byte-for-byte. |
| AntD theme from `web/src/app/providers/AppProviders.tsx` | `ui-kit/src/theme/appTheme.ts` | Theme values preserved; provider/QueryClient composition is now owned by app-shell. |

## CSS ownership split

No selectors, class names, or declaration values were renamed or redesigned.

| Ownership | Target |
|---|---|
| Generic reset, typography, scrollbar, common variables, generic AntD selected-row styling | `ui-kit/src/styles/base.css` |
| Generic AG Grid theme and autosum styling | `ui-kit/src/data-grid/styles.css` |
| Application-shell overflow/root sizing | `app-shell/src/styles.css` |
| Calculation-run selected-row styling | `web/src/modules/calculations/styles.css` |
| Contract-grid selected-row styling | `web/src/modules/contracts/styles.css` |
| GL tree colors/highlights/date markers | `web/src/modules/fin-reports/styles.css` |
| Shared domain observation-date marker | `web/src/shared/ui/styles.css` |

Atomic CSS verification against the original `web/src/styles/global.css`:

```text
original unique selector/property/value facts: 118
result unique selector/property/value facts:   118
missing:                                         0
added:                                           0
```

Combined selectors spanning two owners were split by owner while keeping the same declarations.

## Application import changes

Consumers now use workspace package imports:

```text
@asset-management/ui-kit/theme
@asset-management/ui-kit/data-grid
@asset-management/ui-kit/json-schema
```

Foundation style wiring is owned by `app-shell`; `web` no longer imports UI-kit/root shell CSS directly.

## Tooling and workspace layout

The sibling source package now uses an npm workspace rooted at `frontend/` so TypeScript and Vite resolve a single shared dependency installation instead of trying to resolve React/AntD from `frontend/web/node_modules` while compiling files under `frontend/ui-kit`.

Added:

- `frontend/package.json` with workspaces `web`, `ui-kit`, and `app-shell`;
- `frontend/package-lock.json` as the canonical frontend lockfile;
- `frontend/ui-kit/package.json` with a Stage-1 peer dependency contract;
- root scripts delegating `dev`, `build`, `preview`, `mock`, and `gen-api` to the web workspace.

Changed `web/tsconfig.json`:

- consumes UI kit through package exports;
- no longer needs `../ui-kit/src` in `include` or `@ui-kit` source aliases;
- keeps normal workspace module resolution.

Changed `web/vite.config.ts`:

- removes the temporary `@ui-kit` source alias;
- permits source access within the repository root;
- deduplicates React/AntD/AG Grid/RJSF;
- resolves the Plotly compatibility alias by package name rather than assuming `frontend/web/node_modules`, so npm hoisting to `frontend/node_modules` is safe.

Removed `frontend/web/package-lock.json`; dependency installation/build must now be run from `frontend/`. The UI kit still has no independent build or `dist` output.

## Deliberately left in `frontend/web`

The following were not moved because doing so would require application/domain API changes or would increase regression risk:

- `app/layout/MainLayout.tsx`, `SideMenu.tsx`, and `UserMenu.tsx` now remain only as app-specific compatibility/adaptation layers over `app-shell`.
- `help/HelpDrawer.tsx`
- `shared/ui/PositionSelector.tsx`
- `shared/ui/ObservationDateScenarioControl.tsx`
- `shared/ui/MonitoringSourceTable.tsx`
- `shared/ui/ValuationAnalysisSourceControls.tsx`
- `shared/ui/ValuationScopeFilter.tsx`
- `shared/ui/SimulationCurrencyTargetSelector.tsx`
- other valuation/monitoring/contract-specific controls

These depend on router/store/generated API/domain semantics or are intentionally feature-specific.

`shared/ui/DataTable` and `shared/ui/FormBuilder` were also left in place because they are primarily thin re-exports of third-party libraries and moving them would not materially improve the UI-kit boundary.

## Domain UI candidates

Potential future `frontend/domain-ui` candidates include:

- currency/position selectors;
- observation-date/scenario controls;
- valuation scope/source controls;
- monitoring source controls.

They should not be moved into the base UI kit unless their API is first decoupled from application API/state without changing business semantics.

## Verification

- No `ui-kit/src` imports back into `@app`, `@modules`, `@shared`, generated API, React Router, React Query application code, or Zustand.
- No stale imports of the moved `shared/ui` locations remain in `web/src`.
- Four moved implementation files are byte-identical to the originals.
- CSS semantic split check: 118 facts before / 118 after, 0 missing, 0 added.
- TypeScript parser pass over changed TS/TSX files produced no `TS1xxx` syntax diagnostics.

The workspace lockfile was validated with `npm install --package-lock-only --ignore-scripts --offline`. A full dependency install/build could not be completed in the sandbox because one required tarball was not cached and the online `npm ci` attempt timed out. The archive contains no partial `node_modules`; run `cd frontend && npm ci && npm run build` in the target environment before merge.

## Known pre-existing concern not changed here

The application uses the Vite alias `@common`, while the supplied `web/tsconfig.json` does not define an equivalent explicit `@common/*` path mapping. This extraction does not alter or attempt to fix that unrelated configuration.
