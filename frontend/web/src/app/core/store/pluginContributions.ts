import type { PluginRegistry, PluginRegistryContract } from '@asset-management/app-shell/plugin';
import type { StateCreator } from 'zustand';
import type { ModuleState, RootState } from './types';

export const ZUSTAND_SLICE_CONTRIBUTION = 'web:zustand-slice';
export type ZustandPluginSlice = StateCreator<RootState, [], [], Partial<ModuleState>>;

export function registerZustandSlice<TSlice extends Partial<ModuleState>>(
  registry: PluginRegistryContract,
  key: string,
  slice: StateCreator<RootState, [], [], TSlice>,
) {
  registry.registerContribution(ZUSTAND_SLICE_CONTRIBUTION, key, slice);
}

export function getRegisteredZustandSlices(
  registry: PluginRegistry,
): Record<string, ZustandPluginSlice> {
  return registry.getContributions<ZustandPluginSlice>(ZUSTAND_SLICE_CONTRIBUTION);
}
