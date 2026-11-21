import type { ReactNode } from 'react';
import { Outlet, useLocation } from 'react-router-dom';
import { ApplicationHelpDrawer, type ApplicationHelpConfig } from '../help';
import {
  PluginSideNavigation,
  type PluginMenuSource,
  type SideNavigationItem,
} from '../navigation';
import { useOptionalApplicationCanAccess } from '../runtime';
import { ThemeModeControl } from '../theme/ThemeModeControl';
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
  headerCenter?: ReactNode;
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
  headerCenter,
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
  const resolvedHeaderActions = (
    <>
      <ThemeModeControl />
      {standardHelp}
      {headerActions}
      {standardUserMenu}
    </>
  );

  return (
    <AppShellLayout
      title={title}
      subtitle={subtitle}
      headerCenter={headerCenter}
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
