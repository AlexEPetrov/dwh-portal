import {
  ApartmentOutlined,
  DatabaseOutlined,
  DiffOutlined,
  FundOutlined,
} from '@ant-design/icons';
import type { MenuItem } from '@asset-management/app-shell/plugin';

const menuItems: MenuItem[] = [
  { path: '/objects', label: 'Схема БД', icon: <DatabaseOutlined /> },
  { path: '/storage', label: 'Хранение', icon: <FundOutlined /> },
  { path: '/lineage', label: 'Lineage', icon: <ApartmentOutlined /> },
  { path: '/changes', label: 'Изменения', icon: <DiffOutlined /> },
  { path: '/changes', label: 'Admin', icon: <DiffOutlined /> },
];

export default menuItems;
