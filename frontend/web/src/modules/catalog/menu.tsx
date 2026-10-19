import {
  CommentOutlined,
  DatabaseOutlined,
  FileTextOutlined,
  SettingOutlined,
} from '@ant-design/icons';
import type { MenuItem } from '@asset-management/app-shell/plugin';

const menuItems: MenuItem[] = [
  {
    path: '/assistant',
    label: 'Ассистент',
    icon: <CommentOutlined />,
  },
  {
    path: '/catalog',
    label: 'Каталог данных',
    icon: <DatabaseOutlined />,
    children: [
      { path: '/', label: 'Overview' },
      { path: '/objects', label: 'Схема БД' },
      { path: '/storage', label: 'Хранение' },
      { path: '/lineage', label: 'Lineage' },
      { path: '/changes', label: 'Изменения' },
    ],
  },
  {
    path: '/documents',
    label: 'Документы',
    icon: <FileTextOutlined />,
    children: [{ path: '/documents/upload', label: 'Загрузить' }],
  },
  {
    path: '/admin',
    label: 'Администрирование',
    icon: <SettingOutlined />,
    children: [
      { path: '/admin/extraction-sources', label: 'Редактировать док-источники' },
    ],
  },
];

export default menuItems;
