# Frontend workspace

The frontend is an npm workspace with three source-level packages:

- `web` - the concrete React/Vite business application, business plugins and application-specific adapters/policy;
- `ui-kit` - generic presentation, theme, grids and schema UI;
- `app-shell` - reusable application foundation: bootstrap/providers, runtime adapter contracts, auth/permission UI, main layout, sidebar/navigation, form-page layout, router composition and plugin runtime.

Dependency direction:

```text
web -> app-shell -> ui-kit
```

`app-shell` is intentionally independent from the concrete web state manager and business permission model. `web/src/app/adapters/*` translates the current auth/permission implementation into shell contracts.

Plugin infrastructure is shell-owned, while application-specific plugin state integration is expressed through generic contribution slots. The current web application maps one such slot to Zustand slices; Zustand is not an app-shell dependency.

See [architectural boundaries and hardening evidence](ARCHITECTURE.md) for service scope,
feature-owned server queries, authenticated cache lifetime, module failure policy,
flat-state validation, and future contract blockers.

`ui-kit` and `app-shell` intentionally have no independent `dist` build yet. Their package exports point to source and are consumed through the npm workspace.

## Install

```bash
cd frontend
npm ci
```

Use `npm install` only when intentionally changing dependencies or regenerating `package-lock.json`.

## Development / build

```bash
cd frontend
npm run dev
npm run build
```

The root scripts delegate to the `asset-management-web` workspace.

## Dependency ownership

`frontend/package-lock.json` is the canonical frontend lockfile. Do not maintain nested lockfiles under `web`, `ui-kit` or `app-shell`.
