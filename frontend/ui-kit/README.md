# UI Kit

`frontend/ui-kit` owns generic presentation: theme, common styles, data-grid infrastructure and generic JSON-schema layouts.

It is an independently built ESM library with TypeScript declarations and CSS.
Existing public subpaths resolve to `dist/`, not TypeScript source. Runtime
dependencies remain external peers; no React or component-library copy is bundled.
See [workspace delivery instructions](../README.md) for builds, archive verification
and transfer. The package remains private; registry publication is out of scope.

Import `@asset-management/ui-kit/styles.css` when using UI Kit without App Shell.
App Shell's standard bootstrap imports these foundation styles automatically.
The current foundation includes global styles and an external Google Fonts import;
packaging preserves them, and restricted-network consumers must account for this.

## Public imports

```text
@asset-management/ui-kit/theme
@asset-management/ui-kit/data-grid
@asset-management/ui-kit/json-schema
@asset-management/ui-kit/styles.css
```

## Boundary

```text
web -> app-shell -> ui-kit
web -------------> ui-kit   (direct generic component use is allowed)
```

The UI kit must not depend on application routing, application stores, generated API clients or domain models. Application-shell geometry/auth/router/plugin concerns belong to `frontend/app-shell`, not the UI kit.
