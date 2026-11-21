import { DatabaseOutlined } from '@ant-design/icons';
import type { MenuItem } from '@asset-management/app-shell/plugin';

const menuItems: MenuItem[] = [
  {
    path: '/catalog',
    label: 'Каталог данных',
    icon: <DatabaseOutlined />,
    children: [
      { path: '/', label: 'Обзор' },
      { path: '/objects', label: 'Все объекты' },
      { path: '/storage', label: 'Хранение' },
      { path: '/lineage', label: 'Lineage' },
      { path: '/changes', label: 'Изменения' },
    ],
  },
];

export default menuItems;
