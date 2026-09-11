# UI Kit — Stage 1 source package

`frontend/ui-kit` owns generic presentation: theme, common styles, data-grid infrastructure and generic JSON-schema layouts.

It is an npm workspace source package, not yet an independently built/published library.

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
