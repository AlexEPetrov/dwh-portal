import type { PluginRegistry, PluginRegistryContract } from '@asset-management/app-shell/plugin';
import type { StateCreator } from 'zustand';

export const ZUSTAND_SLICE_CONTRIBUTION = 'web:zustand-slice';
export type ZustandPluginSlice = StateCreator<any>;

export function registerZustandSlice(
  registry: PluginRegistryContract,
  key: string,
  slice: ZustandPluginSlice,
) {
  registry.registerContribution(ZUSTAND_SLICE_CONTRIBUTION, key, slice);
}

export function getRegisteredZustandSlices(
  registry: PluginRegistry,
): Record<string, ZustandPluginSlice> {
  return registry.getContributions<ZustandPluginSlice>(ZUSTAND_SLICE_CONTRIBUTION);
}
