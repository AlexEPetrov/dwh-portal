import { applicationLayout } from '@app/application';
import { initializeStore } from '@app/core/store';
import { getRegisteredZustandSlices } from '@app/core/store/pluginContributions';
import HomePage from '@app/home/HomePage';
import {
  pluginRegistry,
  registerDiscoveredModules,
  type ModuleRegistration,
} from '@asset-management/app-shell/plugin';
import { createStandardApplicationRouter } from '@asset-management/app-shell/routing';

// Vite discovery remains application-owned because import.meta.glob must be
// statically analyzable in the consuming application. Registration semantics
// are owned by app-shell.
const moduleImports = import.meta.glob<ModuleRegistration>('/src/modules/*/index.tsx', {
  import: 'default',
  eager: false,
});

async function loadModules() {
  const moduleRoutes = await registerDiscoveredModules({
    moduleImports,
    registry: pluginRegistry,
    requiredModuleIds: ['catalog', 'documents', 'admin'],
    onModuleLoaded: (path) => console.log('Loaded module:', path),
    onModuleSkipped: (path) => console.log('Skipping disabled module:', path),
  });

  console.log('All registered slices:', Object.keys(getRegisteredZustandSlices(pluginRegistry)));

  // Initialize store AFTER all plugin contributions are registered.
  const store = initializeStore();
  console.log('Store initialized with keys:', Object.keys(store.getState()));

  return moduleRoutes;
}

export const routerPromise = loadModules().then((moduleRoutes) =>
  createStandardApplicationRouter({
    layout: applicationLayout,
    homeElement: <HomePage />,
    routes: moduleRoutes,
  })
);
