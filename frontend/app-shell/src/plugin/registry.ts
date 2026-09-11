import type { MenuItem, PluginRegistryContract } from './types';

export class PluginRegistry implements PluginRegistryContract {
  private contributions = new Map<string, Map<string, unknown>>();
  private menuItems: MenuItem[] = [];

  registerContribution<T>(slot: string, key: string, value: T) {
    let slotContributions = this.contributions.get(slot);
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
    this.menuItems.push(...items);
  }

  getMenuItems(): MenuItem[] {
    return this.menuItems;
  }
}

export const pluginRegistry = new PluginRegistry();
