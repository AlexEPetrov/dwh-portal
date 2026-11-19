import type { ReactNode } from 'react';
import type { RouteObject } from 'react-router-dom';

export interface PermissionRequirement<TAction extends string = string, TContext = unknown> {
  resource: string;
  action: TAction;
  /** Opaque application-owned attributes used by the permission adapter. */
  context?: TContext;
}

export interface MenuItem<TAction extends string = string> {
  path: string;
  label: string;
  strong?: boolean;
  getLabel?: () => ReactNode;
  icon?: ReactNode;
  children?: MenuItem<TAction>[];
  permission?: PermissionRequirement<TAction>;
}

/**
 * State-manager-agnostic plugin contribution registry.
 *
 * Applications define their own contribution slots (for example a Zustand
 * slice slot) and interpret those values outside app-shell.
 */
export interface PluginRegistryContract {
  registerContribution<T>(slot: string, key: string, value: T): void;
  addMenuItems: (...items: MenuItem[]) => void;
}

export interface ModuleRegistration {
  /** Stable application-owned identity, independent of discovery path/order. */
  id: string;
  enabled?: boolean;
  /**
   * Lower values appear earlier in the sidebar when modules are
   * auto-discovered. Omitted order sorts after numbered modules,
   * then by discovery path.
   */
  order?: number;
  menu: MenuItem[];
  routes: () => RouteObject[];
  registerContributions?: (registry: PluginRegistryContract) => void;
}

/** Publishes a complete batch only after every module has been staged successfully. */
export interface ModuleRegistryContract extends PluginRegistryContract {
  registerModules(modules: readonly ModuleRegistration[]): RouteObject[];
}

export type DiscoveredModuleImport = () => Promise<unknown>;
export type DiscoveredModuleImports = Record<string, DiscoveredModuleImport>;
