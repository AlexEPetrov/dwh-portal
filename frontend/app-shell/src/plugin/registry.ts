import type { RouteObject } from 'react-router-dom';
import type { MenuItem, ModuleRegistration, ModuleRegistryContract, PluginRegistryContract } from './types';

function requireKey(value: string, kind: string): void {
  if (typeof value !== 'string' || !value.trim() || value !== value.trim()) {
    throw new Error(`Invalid ${kind}: expected a non-empty, trimmed string`);
  }
}

function pathKey(path: string): string {
  return `/${path.split('/').filter(Boolean).join('/')}`.toLowerCase();
}

function claim(keys: Set<string>, key: string, kind: string): void {
  if (keys.has(key)) throw new Error(`Duplicate ${kind}: ${key}`);
  keys.add(key);
}

function copyMenu(items: MenuItem[]): MenuItem[] {
  return items.map((item) => ({
    ...item,
    ...(item.children ? { children: copyMenu(item.children) } : {}),
  }));
}

export class PluginRegistry implements ModuleRegistryContract {
  private contributions = new Map<string, Map<string, unknown>>();
  private menuItems: MenuItem[] = [];
  private menuPaths = new Set<string>();
  private moduleIds = new Set<string>();
  private routeIds = new Set<string>();
  private routePaths = new Set<string>();

  registerContribution<T>(slot: string, key: string, value: T) {
    requireKey(slot, 'contribution slot');
    requireKey(key, 'contribution key');
    let slotContributions = this.contributions.get(slot);
    if (slotContributions?.has(key)) throw new Error(`Duplicate contribution: ${slot}/${key}`);
    if (!slotContributions) {
      slotContributions = new Map<string, unknown>();
      this.contributions.set(slot, slotContributions);
    }
    slotContributions.set(key, value);
  }

  getContributions<T>(slot: string): Record<string, T> {
    const slotContributions = this.contributions.get(slot);
    if (!slotContributions) return {};
    return Object.fromEntries(slotContributions) as Record<string, T>;
  }

  addMenuItems(...items: MenuItem[]) {
    const paths = new Set(this.menuPaths);
    const validate = (entries: MenuItem[]) => {
      for (const item of entries) {
        requireKey(item.path, 'menu path');
        claim(paths, pathKey(item.path), 'menu path');
        if (item.children) validate(item.children);
      }
    };
    validate(items);
    const copied = copyMenu(items);
    this.menuPaths = paths;
    this.menuItems.push(...copied);
  }

  getMenuItems(): MenuItem[] {
    return copyMenu(this.menuItems);
  }

  registerModules(modules: readonly ModuleRegistration[]): RouteObject[] {
    // Stage the entire batch, including contribution callbacks, without touching
    // the live registry. A failed later module cannot publish earlier modules.
    const staged = new PluginRegistry();
    staged.contributions = new Map(
      Array.from(this.contributions, ([slot, values]) => [slot, new Map(values)])
    );
    staged.menuItems = copyMenu(this.menuItems);
    staged.menuPaths = new Set(this.menuPaths);
    staged.moduleIds = new Set(this.moduleIds);
    staged.routeIds = new Set(this.routeIds);
    staged.routePaths = new Set(this.routePaths);

    const routes: RouteObject[] = [];
    for (const module of modules) {
      requireKey(module.id, 'module id');
      claim(staged.moduleIds, module.id, 'module id');
      if (module.enabled === false) throw new Error(`Cannot register disabled module: ${module.id}`);
      try {
        staged.addMenuItems(...module.menu);
        const moduleRoutes = module.routes();
        if (!Array.isArray(moduleRoutes)) throw new Error('Expected an array of routes');
        routes.push(...staged.stageRoutes(moduleRoutes));

        // Expose writes only, and reject retained/async writes after staging.
        let active = true;
        const assertActive = () => {
          if (!active) throw new Error(`Registration has closed for module: ${module.id}`);
        };
        const writer: PluginRegistryContract = {
          addMenuItems: (...items) => {
            assertActive();
            staged.addMenuItems(...items);
          },
          registerContribution: (slot, key, value) => {
            assertActive();
            staged.registerContribution(slot, key, value);
          },
        };
        try {
          const result: unknown = module.registerContributions?.(writer);
          if (result !== undefined) {
            // An accidentally async callback may reject after its writer closes.
            // Report the synchronous contract violation without an unhandled rejection.
            void Promise.resolve(result).catch(() => { });
            throw new Error('Contribution registration must be synchronous and return nothing');
          }
        } finally {
          active = false;
        }
      } catch (error) {
        throw new Error(`Failed to register module "${module.id}": ${String(error)}`);
      }
    }

    this.contributions = staged.contributions;
    this.menuItems = staged.menuItems;
    this.menuPaths = staged.menuPaths;
    this.moduleIds = staged.moduleIds;
    this.routeIds = staged.routeIds;
    this.routePaths = staged.routePaths;
    return routes;
  }

  private stageRoutes(routes: RouteObject[], parentPath = ''): RouteObject[] {
    return routes.map((route) => {
      if (route.id !== undefined) {
        requireKey(route.id, 'route id');
        claim(this.routeIds, route.id, 'route id');
      }
      if (route.index && route.children) throw new Error('Index routes cannot have children');
      if (route.path !== undefined && typeof route.path !== 'string') {
        throw new Error('Invalid route path');
      }
      const fullPath = route.path?.startsWith('/')
        ? route.path
        : `${parentPath}/${route.path ?? ''}`;
      if (route.path !== undefined || route.index) {
        // Parameter names do not distinguish router matches. Keep index routes
        // distinct from their parent layout at the same URL.
        const pattern = pathKey(fullPath).replace(/:[^/]+/g, (part) => part.endsWith('?') ? ':?' : ':');
        claim(this.routePaths, `${route.index ? 'index' : 'path'}:${pattern}`, 'route path');
      }
      return {
        ...route,
        ...(route.children ? { children: this.stageRoutes(route.children, fullPath) } : {}),
      } as RouteObject;
    });
  }
}

export const pluginRegistry = new PluginRegistry();
