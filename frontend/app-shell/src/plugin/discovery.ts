import type { RouteObject } from 'react-router-dom';
import type { DiscoveredModuleImports, ModuleRegistration, ModuleRegistryContract } from './types';

export interface RegisterDiscoveredModulesOptions {
  moduleImports: DiscoveredModuleImports;
  registry: ModuleRegistryContract;
  /** These identities must be discovered and enabled. All import/registration errors are fatal. */
  requiredModuleIds?: readonly string[];
  onModuleLoaded?: (path: string, module: ModuleRegistration) => void;
  onModuleSkipped?: (path: string) => void;
}

function moduleSortKey(path: string, module: ModuleRegistration): [number, string] {
  const order = module.order ?? Number.MAX_SAFE_INTEGER;
  return [order, path];
}

function validateModule(value: unknown, path: string): asserts value is ModuleRegistration {
  if (typeof value !== 'object' || value === null) {
    throw new Error(`Invalid module export: ${path}`);
  }
  const module = value as Partial<ModuleRegistration>;
  if (
    typeof module.id !== 'string' || !module.id.trim() || module.id !== module.id.trim() ||
    (module.enabled !== undefined && typeof module.enabled !== 'boolean') ||
    (module.order !== undefined && !Number.isFinite(module.order)) ||
    !Array.isArray(module.menu) || typeof module.routes !== 'function' ||
    (module.registerContributions !== undefined && typeof module.registerContributions !== 'function')
  ) {
    throw new Error(`Invalid module registration: ${path}`);
  }
}

export async function registerDiscoveredModules({
  moduleImports,
  registry,
  requiredModuleIds = [],
  onModuleLoaded,
  onModuleSkipped,
}: RegisterDiscoveredModulesOptions): Promise<RouteObject[]> {
  const loaded: Array<{ path: string; module: ModuleRegistration }> = [];
  // Imports may run in parallel; publication and ordering remain deterministic.
  // There is deliberately no catch-and-skip policy for broken modules.
  const discovered = await Promise.all(Object.keys(moduleImports).sort().map(async (path) => {
    let module: unknown;
    try {
      module = await moduleImports[path]();
    } catch (error) {
      throw new Error(`Failed to import module "${path}": ${String(error)}`);
    }
    validateModule(module, path);
    return { path, module };
  }));
  const identities = new Set<string>();
  for (const { path, module } of discovered) {
    if (identities.has(module.id)) throw new Error(`Duplicate module id "${module.id}" at ${path}`);
    identities.add(module.id);
    if (module.enabled !== false) loaded.push({ path, module });
  }
  for (const id of requiredModuleIds) {
    if (!loaded.some(({ module }) => module.id === id)) {
      throw new Error(`Required module is missing or disabled: ${id}`);
    }
  }

  loaded.sort((a, b) => {
    const [ao, ap] = moduleSortKey(a.path, a.module);
    const [bo, bp] = moduleSortKey(b.path, b.module);
    if (ao !== bo) return ao - bo;
    return ap.localeCompare(bp);
  });

  const routes = registry.registerModules(loaded.map(({ module }) => module));
  // Observers run only after successful publication, never during staging.
  for (const { path, module } of discovered) {
    if (module.enabled === false) onModuleSkipped?.(path);
  }
  for (const { path, module } of loaded) onModuleLoaded?.(path, module);

  return routes;
}
