# App Shell extraction report

## Source of truth

This revision is based on the latest `frontend3-app-shell-cleanup-tsfix` state derived from the uploaded `frontend(3).zip`.

Priority: move generic application mechanics into `app-shell` while preserving current business behavior and keeping concrete application policy/state in `web`.

## Shell-owned after this revision

- React root/provider/router bootstrap;
- application runtime adapter contracts;
- standard auth/login/permission/user-menu wiring;
- standard application layout and router composition;
- main application chrome and current delayed collapsed-sidebar preview behavior;
- plugin-backed sidebar/navigation;
- `MainFormLayout`;
- plugin contract, registry and discovery orchestration;
- state-manager-agnostic plugin contribution registry;
- shell CSS and UI-kit CSS bootstrap.

## Removed from web

The following wiring components are no longer needed in the concrete application:

- `app/layout/MainLayout.tsx`;
- `app/layout/SideMenu.tsx`;
- `app/layout/UserMenu.tsx`;
- `app/router/LoginPage.tsx`;
- `app/router/RequireAuth.tsx`;
- `app/router/RequirePermission.tsx`.

Business modules use the shell `ApplicationPermissionGuard` directly. The concrete app describes shell metadata in `app/application.tsx`.

## Application adapters remaining in web

- `app/adapters/authAdapter.ts` bridges the current Zustand/backend auth state to `AuthAdapter`;
- `app/adapters/permissionAdapter.ts` bridges ATRM `Action`/`canPerform`/permissions to `PermissionAdapter`;
- `app/core/store/pluginContributions.ts` maps a generic plugin contribution slot to current Zustand `StateCreator` values.

These files are intentionally in `web`: they are the translation boundary between this application's implementation choices and the generic platform contract.

## Zustand decoupling

`app-shell` no longer imports `zustand`, exposes `StateCreator`, or has a Zustand peer dependency.

The previous plugin API:

```text
registerStoreSlices / registerStoreSlice / getStoreSlices
```

was replaced with generic contributions:

```text
registerContributions / registerContribution / getContributions
```

The concrete web application defines the `web:zustand-slice` contribution slot and consumes it before `initializeStore()`. Registration order and dynamic-store behavior remain unchanged.

## Deliberately remaining in web

- generated API and transport wrappers;
- concrete auth/session implementation;
- role/action/resource permission model;
- root Zustand store and business module slices;
- application HomePage/help implementation;
- business plugins/modules/pages/components;
- ATRM-specific event names and application labels/navigation metadata.

## Verification

- package-lock regenerated successfully with `npm install --package-lock-only --ignore-scripts --offline`;
- source scan confirms no `zustand`, `@app`, `@modules`, `@shared`, `RootState`, `canPerform` or ATRM event dependency in `app-shell`;
- stale web layout/auth wrapper imports removed;
- stale `registerStoreSlices` / `registerStoreSlice` / `getStoreSlices` calls removed;
- TypeScript syntax parsing completed over frontend TS/TSX sources with zero syntax diagnostics;
- full build could not complete in the sandbox because `npm ci` was interrupted and left incomplete `@types/*` directories; the resulting TS2688 errors are dependency-installation errors rather than source diagnostics.

Canonical target-environment verification:

```bash
cd frontend
rm -rf node_modules
npm ci
npm run build
```

## Final foundation cleanup (2026-09-06)

- Moved contextual Help mechanics into `app-shell/src/help/**`; `web` now owns only help topic data and markdown content.
- `ApplicationLayout` renders configured standard Help automatically.
- Added shell-owned `RouteSuspense` and removed duplicated per-plugin suspense wrappers.
- Added shell-owned `ApplicationCan` for conditional permission-aware rendering.
- Extended `PermissionRequirement` with opaque `context`; only the web `PermissionAdapter` interprets it as ATRM constraints.
- Removed dead `web/src/App.tsx` and unused zero-value `DataTable` / `FormBuilder` wrappers.
- Kept `web/src/app/router/index.tsx` and `web/src/main.tsx` application-owned because they contain Vite discovery, state contribution initialization, MSW/locale and adapter composition.
