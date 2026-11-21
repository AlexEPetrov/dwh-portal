import type { ApplicationLayoutProps } from '@asset-management/app-shell/layout';
import { pluginRegistry } from '@asset-management/app-shell/plugin';
import { HeaderNavigation } from './adapters/HeaderNavigation';
import './application.css';

const MENU_LABEL_REFRESH_EVENT = 'atrm:menu-label-refresh';

/**
 * Application-owned metadata/policy for the standard shell.
 * Rendering mechanics live in app-shell; this file only describes this app.
 */
export const applicationLayout = {
  title: 'DWH Portal',
  subtitle: 'Каталог объектов DWH, хранение, lineage и структурные изменения.',
  headerCenter: <HeaderNavigation />,
  expandSidebarLabel: 'Развернуть меню',
  collapseSidebarLabel: 'Свернуть меню',
  navigation: {
    registry: pluginRegistry,
    defaultOpenKeys: ['/catalog'],
    labelRefreshEvents: [MENU_LABEL_REFRESH_EVENT],
    refreshLabelsOnStorage: true,
  },
} satisfies ApplicationLayoutProps;
