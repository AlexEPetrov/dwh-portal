import type { RouteObject } from 'react-router-dom';
import type { DiscoveredModuleImports, ModuleRegistration, PluginRegistryContract } from './types';

export interface RegisterDiscoveredModulesOptions {
  moduleImports: DiscoveredModuleImports;
  registry: PluginRegistryContract;
  onModuleLoaded?: (path: string, module: ModuleRegistration) => void;
  onModuleSkipped?: (path: string) => void;
}

function moduleSortKey(path: string, module: ModuleRegistration): [number, string] {
  const order = module.order ?? Number.MAX_SAFE_INTEGER;
  return [order, path];
}

export async function registerDiscoveredModules({
  moduleImports,
  registry,
  onModuleLoaded,
  onModuleSkipped,
}: RegisterDiscoveredModulesOptions): Promise<RouteObject[]> {
  const routes: RouteObject[] = [];
  const loaded: Array<{ path: string; module: ModuleRegistration }> = [];

  for (const path of Object.keys(moduleImports)) {
    const imported = await moduleImports[path]();
    const module = imported as ModuleRegistration;

    if (module.enabled === false) {
      onModuleSkipped?.(path);
      continue;
    }

    loaded.push({ path, module });
  }

  loaded.sort((a, b) => {
    const [ao, ap] = moduleSortKey(a.path, a.module);
    const [bo, bp] = moduleSortKey(b.path, b.module);
    if (ao !== bo) return ao - bo;
    return ap.localeCompare(bp);
  });

  for (const { path, module } of loaded) {
    registry.addMenuItems(...module.menu);
    module.registerContributions?.(registry);
    routes.push(...module.routes());
    onModuleLoaded?.(path, module);
  }

  return routes;
}
