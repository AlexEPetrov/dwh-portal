import { HomeOutlined } from '@ant-design/icons';
import type { ApplicationLayoutProps } from '@asset-management/app-shell/layout';
import { pluginRegistry } from '@asset-management/app-shell/plugin';
import { HELP_TOPICS } from '../help/topics';

const MENU_LABEL_REFRESH_EVENT = 'atrm:menu-label-refresh';

/**
 * Application-owned metadata/policy for the standard shell.
 * Rendering mechanics live in app-shell; this file only describes this app.
 */
export const applicationLayout = {
  title: 'DWH Portal',
  subtitle: 'Каталог объектов DWH, хранение, lineage и структурные изменения.',
  expandSidebarLabel: 'Развернуть меню',
  collapseSidebarLabel: 'Свернуть меню',
  help: { topics: HELP_TOPICS },
  navigation: {
    registry: pluginRegistry,
    prependItems: [
      {
        path: '/',
        label: 'Overview',
        icon: <HomeOutlined />,
      },
    ],
    defaultOpenKeys: ['/objects', '/storage'],
    labelRefreshEvents: [MENU_LABEL_REFRESH_EVENT],
    refreshLabelsOnStorage: true,
  },
} satisfies ApplicationLayoutProps;
