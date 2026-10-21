import { FileTextOutlined } from '@ant-design/icons';
import type { MenuItem } from '@asset-management/app-shell/plugin';

const menuItems: MenuItem[] = [
  {
    path: '/documents',
    label: 'Документы',
    icon: <FileTextOutlined />,
    children: [{ path: '/documents/upload', label: 'Загрузить' }],
  },
];

export default menuItems;
