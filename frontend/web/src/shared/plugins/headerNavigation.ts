import type { PluginRegistryContract } from '@asset-management/app-shell/plugin';

export const HEADER_NAVIGATION_CONTRIBUTION = 'portal.header-navigation';

export interface HeaderNavigationItem {
    label: string;
    path: string;
    order?: number;
}

/** Modules own destinations; the application owns their header presentation. */
export function registerHeaderNavigation(
    registry: PluginRegistryContract,
    key: string,
    item: HeaderNavigationItem,
) {
    registry.registerContribution(HEADER_NAVIGATION_CONTRIBUTION, key, item);
}
