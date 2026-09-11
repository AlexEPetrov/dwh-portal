import { useNavigate } from 'react-router-dom';
import { useApplicationAuth } from '../runtime';
import { UserMenu, type UserMenuProps } from './UserMenu';

export interface ApplicationUserMenuProps
  extends Omit<UserMenuProps, 'user' | 'onLogout'> {
  loginPath?: string;
}

export function ApplicationUserMenu({ loginPath = '/login', ...props }: ApplicationUserMenuProps) {
  const navigate = useNavigate();
  const { user, logout } = useApplicationAuth();

  const handleLogout = async () => {
    try {
      await logout();
    } catch (error) {
      console.error('Logout failed:', error);
    } finally {
      navigate(loginPath, { replace: true });
    }
  };

  return <UserMenu {...props} user={user} onLogout={handleLogout} />;
}
