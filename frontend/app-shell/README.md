# @asset-management/app-shell

Reusable application foundation for intranet and multi-purpose React applications.

## Responsibility

`app-shell` owns the common application machinery that should not be copied into App2/App3:

- React/application bootstrap and common providers;
- application runtime adapter contracts for auth and permissions;
- standard login/auth/permission/user-menu wiring through those adapters;
- main application chrome and collapsed/preview sidebar behavior;
- plugin-aware sidebar/navigation assembled from plugin metadata;
- `MainFormLayout` page/form template;
- router composition, including a standard application router;
- plugin contracts, registry and discovery/registration orchestration;
- generic plugin contribution slots;
- shell-specific viewport/layout CSS;
- automatic UI-kit foundation CSS loading through `renderApplication`.

## Boundary

Allowed direction:

```text
web -> app-shell -> ui-kit
```

`app-shell` must not know or import:

- generated API clients from an application;
- Zustand, Redux or another concrete application state manager;
- application `RootState` or store shape;
- application `Action`/role/permission types or `canPerform` implementation;
- business modules or domain models;
- application-specific events/content such as ATRM help or label refresh names.

Instead, applications bridge their implementation through generic adapters:

```text
web auth/store ----------------> AuthAdapter -----------\
web permission model ----------> PermissionAdapter -----+--> app-shell
web module state registration -> contribution adapter -/
```

Plugin contributions are state-manager agnostic. A consuming application may define a contribution slot for Zustand slices, Redux reducers, services, widgets, or other extension data without making those technologies part of the shell contract.

The package is source-level in this stage and has no independent library build yet.

## Standard capabilities

The shell owns reusable application mechanics such as plugin navigation, auth/permission guards,
contextual help rendering, standard lazy-route suspense, user menu, and application layouts.
Applications provide business metadata/content and concrete auth/permission adapters.

- `@asset-management/app-shell/help` — contextual help drawer and markdown renderer; applications own topic content.
- `@asset-management/app-shell/routing` — standard route composition and `RouteSuspense`.
- `@asset-management/app-shell/auth` — auth/permission guards and `ApplicationCan`.

## Module publication and failures

Each module declares a stable, non-empty `ModuleRegistration.id`. Discovery paths
and menu order are not identities. Applications declare `requiredModuleIds` at
discovery: a missing or disabled required identity prevents startup. There is no
implicit optional-module policy: every import, malformed export, collision, route
factory failure, or contribution callback failure rejects discovery. Only an
explicit `enabled: false` skips an otherwise valid, non-required module.

Imports run in parallel, followed by deterministic order/path sorting. The registry
stages the complete enabled batch and publishes only after all registrations pass.
Module IDs, explicit route IDs, route match patterns, recursive menu paths, and
contribution slot/key pairs must be unique, including against prior registrations.
Route/menu paths are conservatively compared without case or redundant slashes;
parameter names do not distinguish route patterns. Index routes are distinct from
their parent layouts. This detects duplicate identities, not every possible
overlap between optional parameters, static routes, and wildcards.

Contribution callbacks must be synchronous, return nothing, and only register
through the supplied writer. Retained writers are closed after the callback.
Opaque contribution values are not deep-cloned: callbacks and module imports must
not mutate existing values or perform external side effects expecting rollback.
Discovery observers run after publication and must not throw.

`RouteSuspense` must be rendered inside a router. It catches lazy import/render
failures locally, resets on navigation, and provides a full reload action for
failed cached chunk imports. Applications can override loading/error fallbacks.
