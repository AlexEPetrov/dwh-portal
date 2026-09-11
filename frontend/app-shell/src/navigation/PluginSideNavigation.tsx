import type { ReactNode } from 'react';
import { useEffect, useReducer } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import type { MenuItem, PermissionRequirement } from '../plugin';
import { SideNavigation, type SideNavigationItem } from './SideNavigation';

const EMPTY_REFRESH_EVENTS: string[] = [];

export interface PluginMenuSource<TAction extends string = string> {
  getMenuItems(): MenuItem<TAction>[];
}

export interface PluginSideNavigationProps<TAction extends string = string> {
  collapsed: boolean;
  registry: PluginMenuSource<TAction>;
  canAccess?: (permission: PermissionRequirement<TAction>) => boolean;
  prependItems?: SideNavigationItem[];
  defaultOpenKeys?: string[];
  /** Optional application events that invalidate dynamic plugin labels. */
  labelRefreshEvents?: string[];
  /** Re-resolve dynamic labels when browser storage changes. */
  refreshLabelsOnStorage?: boolean;
}

const resolveMenuLabel = <TAction extends string>(item: MenuItem<TAction>): ReactNode =>
  item.getLabel ? item.getLabel() : item.label;

const filterMenuItems = <TAction extends string>(
  items: MenuItem<TAction>[],
  canAccess?: (permission: PermissionRequirement<TAction>) => boolean,
): MenuItem<TAction>[] => items
  .map((item) => ({
    ...item,
    children: item.children ? filterMenuItems(item.children, canAccess) : undefined,
  }))
  .filter((item) => {
    const permitted = !item.permission || (canAccess ? canAccess(item.permission) : false);
    const hasVisibleChildren = !item.children || item.children.length > 0;
    return permitted && hasVisibleChildren;
  });

const toNavigationItems = <TAction extends string>(items: MenuItem<TAction>[]): SideNavigationItem[] =>
  items.map((item) => ({
    path: item.path,
    label: resolveMenuLabel(item),
    icon: item.icon,
    strong: item.strong,
    children: item.children ? toNavigationItems(item.children) : undefined,
  }));

/**
 * Router-aware navigation assembled from plugin metadata.
 *
 * The shell owns menu assembly, recursive permission filtering, dynamic label
 * resolution and route navigation. Applications only provide their permission
 * policy and optional app-specific entries/events that trigger a re-render.
 */
export function PluginSideNavigation<TAction extends string = string>({
  collapsed,
  registry,
  canAccess,
  prependItems = [],
  defaultOpenKeys = [],
  labelRefreshEvents = EMPTY_REFRESH_EVENTS,
  refreshLabelsOnStorage = false,
}: PluginSideNavigationProps<TAction>) {
  const location = useLocation();
  const navigate = useNavigate();
  const [, forceLabelRefresh] = useReducer((revision: number) => revision + 1, 0);

  useEffect(() => {
    if (typeof window === 'undefined') return;

    const handler = () => forceLabelRefresh();
    for (const eventName of labelRefreshEvents) {
      window.addEventListener(eventName, handler);
    }
    if (refreshLabelsOnStorage) {
      window.addEventListener('storage', handler);
    }

    return () => {
      for (const eventName of labelRefreshEvents) {
        window.removeEventListener(eventName, handler);
      }
      if (refreshLabelsOnStorage) {
        window.removeEventListener('storage', handler);
      }
    };
  }, [labelRefreshEvents, refreshLabelsOnStorage]);

  const visiblePluginItems = filterMenuItems(registry.getMenuItems(), canAccess);
  const navigationItems = [
    ...prependItems,
    ...toNavigationItems(visiblePluginItems),
  ];

  return (
    <SideNavigation
      collapsed={collapsed}
      currentPath={location.pathname}
      items={navigationItems}
      defaultOpenKeys={defaultOpenKeys}
      onNavigate={(path) => navigate(path)}
    />
  );
}
