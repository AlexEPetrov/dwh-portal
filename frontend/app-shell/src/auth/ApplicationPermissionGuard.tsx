import type { ReactNode } from 'react';
import type { PermissionRequirement } from '../plugin';
import { useApplicationCanAccess } from '../runtime';
import { RequirePermission } from './RequirePermission';

export interface ApplicationPermissionGuardProps {
  permission: PermissionRequirement;
  children: ReactNode;
  title?: string;
  subTitle?: string;
}

export function ApplicationPermissionGuard({
  permission,
  children,
  title,
  subTitle,
}: ApplicationPermissionGuardProps) {
  const canAccess = useApplicationCanAccess();
  return (
    <RequirePermission allowed={canAccess(permission)} title={title} subTitle={subTitle}>
      {children}
    </RequirePermission>
  );
}
