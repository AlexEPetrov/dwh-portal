import type { ReactNode } from 'react';
import { ApplicationHelpDrawer, type ApplicationHelpConfig } from '../help';
import { Outlet, useLocation } from 'react-router-dom';
import {
  PluginSideNavigation,
  type PluginMenuSource,
  type SideNavigationItem,
} from '../navigation';
import { useOptionalApplicationCanAccess } from '../runtime';
import { ApplicationUserMenu, type ApplicationUserMenuProps } from '../user/ApplicationUserMenu';
import { AppShellLayout } from './AppShellLayout';

export interface ApplicationNavigationConfig {
  registry: PluginMenuSource;
  prependItems?: SideNavigationItem[];
  defaultOpenKeys?: string[];
  labelRefreshEvents?: string[];
  refreshLabelsOnStorage?: boolean;
}

export interface ApplicationLayoutProps {
  title: ReactNode;
  subtitle?: ReactNode;
  navigation: ApplicationNavigationConfig;
  help?: ApplicationHelpConfig;
  headerActions?: ReactNode;
  showUserMenu?: boolean;
  userMenu?: ApplicationUserMenuProps;
  headerHeight?: number;
  sidebarWidth?: number;
  collapsedSidebarWidth?: number;
  sidebarHoverDelay?: number;
  expandSidebarLabel?: string;
  collapseSidebarLabel?: string;
}

/**
 * Standard application layout: shell-owned layout + plugin navigation + user menu.
 * Applications provide metadata and adapters; they do not implement sidebar wiring.
 */
export function ApplicationLayout({
  title,
  subtitle,
  navigation,
  help,
  headerActions,
  showUserMenu = true,
  userMenu,
  headerHeight,
  sidebarWidth,
  collapsedSidebarWidth,
  sidebarHoverDelay,
  expandSidebarLabel,
  collapseSidebarLabel,
}: ApplicationLayoutProps) {
  const location = useLocation();
  const canAccess = useOptionalApplicationCanAccess();

  const standardHelp = help ? <ApplicationHelpDrawer {...help} /> : null;
  const standardUserMenu = showUserMenu ? <ApplicationUserMenu {...userMenu} /> : null;
  const resolvedHeaderActions = standardHelp || headerActions || standardUserMenu
    ? (
      <>
        {standardHelp}
        {headerActions}
        {standardUserMenu}
      </>
    )
    : undefined;

  return (
    <AppShellLayout
      title={title}
      subtitle={subtitle}
      navigationKey={location.pathname}
      headerActions={resolvedHeaderActions}
      headerHeight={headerHeight}
      sidebarWidth={sidebarWidth}
      collapsedSidebarWidth={collapsedSidebarWidth}
      sidebarHoverDelay={sidebarHoverDelay}
      expandSidebarLabel={expandSidebarLabel}
      collapseSidebarLabel={collapseSidebarLabel}
      renderSidebar={(collapsed) => (
        <PluginSideNavigation
          collapsed={collapsed}
          registry={navigation.registry}
          canAccess={canAccess}
          prependItems={navigation.prependItems}
          defaultOpenKeys={navigation.defaultOpenKeys}
          labelRefreshEvents={navigation.labelRefreshEvents}
          refreshLabelsOnStorage={navigation.refreshLabelsOnStorage}
        />
      )}
    >
      <Outlet />
    </AppShellLayout>
  );
}
