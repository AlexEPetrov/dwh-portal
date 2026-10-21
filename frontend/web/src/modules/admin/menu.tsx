import { SettingOutlined } from '@ant-design/icons';
import type { MenuItem } from '@asset-management/app-shell/plugin';

const menuItems: MenuItem[] = [
  {
    path: '/admin',
    label: 'Администрирование',
    icon: <SettingOutlined />,
    permission: { resource: 'admin', action: 'edit' },
    children: [
      {
        path: '/admin/extraction-sources',
        label: 'Редактировать док-источники',
        permission: { resource: 'admin', action: 'edit' },
      },
    ],
  },
];

export default menuItems;
