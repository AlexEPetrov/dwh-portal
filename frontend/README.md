# Frontend workspace

The frontend is an npm workspace with an application and two independently built libraries:

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

`ui-kit` and `app-shell` export built ESM, TypeScript declarations and CSS from
their own `dist/` directories. Public package names and subpaths are unchanged.
Neither library bundles React or other third-party dependencies. The workspace
application consumes the same built exports as an external archive consumer.

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

The root application scripts delegate to the `asset-management-web` workspace.
Its development, mock and production build lifecycle first builds UI Kit, then
App Shell. No source aliases are needed. After editing library sources during an
existing dev session, run `npm run build:packages` again; library-source HMR is
not provided by this build-output consumption mode.

## Library build, verification and delivery

Run from `frontend/`:

```bash
npm run build:packages
npm run verify:packages
npm run pack:packages
```

Individual builds are also available with `npm run build --workspace=@asset-management/ui-kit`
and `npm run build --workspace=@asset-management/app-shell`; build UI Kit first.
Repository build tooling is shared under `frontend/scripts/`, not shipped in the
archives. Consumers need neither these scripts nor TypeScript source compilation.

Transfer both archives together:

```text
frontend/artifacts/asset-management-ui-kit-0.1.0.tgz
frontend/artifacts/asset-management-app-shell-0.1.0.tgz
```

In a separate application, install both local archives in one npm invocation
(adjust the archive paths to their transferred locations), along with compatible
peer dependencies declared in each package manifest. Installing UI Kit alone is
supported; App Shell depends on UI Kit. Both packages deliberately remain
`private: true`: no registry publication or registry selection is part of this
change. An eventual registry release requires a separate publication decision.

The package verifier packs actual archives, extracts their payloads outside the
repository and checks every public entry, library-owned declarations, and a Vite
consumer build including CSS. It reuses installed third-party dependencies via
symlinks, never the workspace library links. It performs no network install and
does not claim fresh registry resolution or browser interaction coverage.

Current third-party declaration limitations: installed Ant Design references
React's unavailable `ActionDispatch` type, and rc-picker has a nullable
`defaultValue` inheritance mismatch. These two diagnostics are printed separately;
our emitted declaration and consumer errors still fail verification. The portal
retains its existing `skipLibCheck` setting. The isolated Vite build also reports
upstream ignored `use client` directives.

See [the package workflow](../rules/workflows/frontend-packages.md) for registered
verification and [architectural boundaries](ARCHITECTURE.md) for ownership.

## Dependency ownership

`frontend/package-lock.json` is the canonical frontend lockfile. Do not maintain nested lockfiles under `web`, `ui-kit` or `app-shell`.
