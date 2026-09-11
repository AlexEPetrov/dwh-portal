import { Result } from 'antd';
import type { ReactNode } from 'react';

export interface RequirePermissionProps {
  allowed: boolean;
  children: ReactNode;
  title?: string;
  subTitle?: string;
}

export function RequirePermission({
  allowed,
  children,
  title = 'Нет доступа',
  subTitle = 'Недостаточно прав для просмотра этого раздела.',
}: RequirePermissionProps) {
  if (!allowed) {
    return <Result status="403" title={title} subTitle={subTitle} />;
  }

  return <>{children}</>;
}
