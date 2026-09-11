import type { RouteObject } from 'react-router-dom';
import type { DiscoveredModuleImports, ModuleRegistration, PluginRegistryContract } from './types';

export interface RegisterDiscoveredModulesOptions {
  moduleImports: DiscoveredModuleImports;
  registry: PluginRegistryContract;
  onModuleLoaded?: (path: string, module: ModuleRegistration) => void;
  onModuleSkipped?: (path: string) => void;
}

export async function registerDiscoveredModules({
  moduleImports,
  registry,
  onModuleLoaded,
  onModuleSkipped,
}: RegisterDiscoveredModulesOptions): Promise<RouteObject[]> {
  const routes: RouteObject[] = [];

  for (const path of Object.keys(moduleImports)) {
    const imported = await moduleImports[path]();
    const module = imported as ModuleRegistration;

    if (module.enabled === false) {
      onModuleSkipped?.(path);
      continue;
    }

    registry.addMenuItems(...module.menu);
    module.registerContributions?.(registry);
    routes.push(...module.routes());
    onModuleLoaded?.(path, module);
  }

  return routes;
}
