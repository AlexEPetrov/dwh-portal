import { LogoutOutlined, SettingOutlined, UserOutlined } from '@ant-design/icons';
import type { MenuProps } from 'antd';
import { Avatar, Dropdown, Space, Typography } from 'antd';

const { Text } = Typography;

export interface AppShellUser {
  name?: string | null;
  email?: string | null;
}

export interface UserMenuProps {
  user?: AppShellUser | null;
  onLogout: () => void | Promise<void>;
  settingsLabel?: string;
  logoutLabel?: string;
  settingsDisabled?: boolean;
}

export function UserMenu({
  user,
  onLogout,
  settingsLabel = 'Settings',
  logoutLabel = 'Logout',
  settingsDisabled = true,
}: UserMenuProps) {
  const handleLogout = async () => {
    await onLogout();
  };

  const menuItems: MenuProps['items'] = [
    {
      key: 'user',
      label: (
        <Space direction="vertical" size={0}>
          <Text strong>{user?.name || 'User'}</Text>
          <Text type="secondary" style={{ fontSize: 12 }}>
            {user?.email || ''}
          </Text>
        </Space>
      ),
      disabled: true,
    },
    { type: 'divider' },
    {
      key: 'settings',
      icon: <SettingOutlined />,
      label: settingsLabel,
      disabled: settingsDisabled,
    },
    { type: 'divider' },
    {
      key: 'logout',
      icon: <LogoutOutlined />,
      label: logoutLabel,
      danger: true,
      onClick: () => void handleLogout(),
    },
  ];

  return (
    <Dropdown menu={{ items: menuItems }} trigger={['click']} placement="bottomRight">
      <Space style={{ cursor: 'pointer', padding: '0 8px' }}>
        <Avatar icon={<UserOutlined />} size="small" />
        <Text>{user?.name || 'User'}</Text>
      </Space>
    </Dropdown>
  );
}
