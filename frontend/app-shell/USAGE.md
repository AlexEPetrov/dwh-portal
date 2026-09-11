# App Shell usage

## Runtime adapters

The shell understands that an application may have authentication and a permission model, but it does not know how either is implemented.

```ts
const authAdapter: AuthAdapter = {
  useAuthState() {
    // read from the application's own state/auth implementation
    return { user, isAuthenticated, isLoading, login, logout, bootstrapSession };
  },
};

const permissionAdapter: PermissionAdapter = {
  useCanAccess() {
    return (requirement) => applicationPermissionPolicy(requirement);
  },
};
```

Pass them once at bootstrap:

```tsx
renderApplication({
  root: document.getElementById('root')!,
  router,
  locale,
  runtime: {
    auth: authAdapter,
    permissions: permissionAdapter,
  },
});
```

The standard shell login, auth boundary, user menu, plugin navigation and permission guard consume those adapters internally.

## Standard layout/router

Applications normally provide metadata rather than implementing `MainLayout`, `SideMenu`, `UserMenu` and auth wrapper components themselves:

```tsx
const layout = {
  title: 'Application',
  subtitle: 'Description',
  headerActions: <ApplicationHelp />,
  navigation: {
    registry: pluginRegistry,
    prependItems: [homeItem],
    defaultOpenKeys: ['/reports'],
  },
} satisfies ApplicationLayoutProps;

const router = createStandardApplicationRouter({
  layout,
  homeElement: <HomePage />,
  routes: pluginRoutes,
});
```

The shell owns collapse/expand, delayed preview, recursive plugin-menu filtering, permission evaluation calls, router matching/navigation and the standard user menu.

## Form page template

```tsx
<MainFormLayout title="Edit entity" header={breadcrumbs} actions={actions}>
  <EntityForm />
</MainFormLayout>
```

## Plugins

The consuming Vite application keeps the physical discovery expression because `import.meta.glob` must be statically analyzable there:

```tsx
const moduleImports = import.meta.glob<ModuleRegistration>('/src/modules/*/index.tsx', {
  import: 'default',
  eager: false,
});
```

Registration semantics belong to the shell:

```tsx
const routes = await registerDiscoveredModules({
  moduleImports,
  registry: pluginRegistry,
});
```

A plugin/module contributes menu metadata, routes and optional generic contributions:

```ts
const registerContributions: ModuleRegistration['registerContributions'] = (registry) => {
  registry.registerContribution('application-defined-slot', 'key', value);
};
```

The meaning of a contribution slot is application-owned. `app-shell` does not import or depend on the technology behind it.
