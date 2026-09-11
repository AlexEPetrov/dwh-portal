import type { ReactNode } from 'react';
import type { PermissionRequirement } from '../plugin';
import { useApplicationCanAccess } from '../runtime';

export interface ApplicationCanProps {
  permission: PermissionRequirement;
  children: ReactNode;
  fallback?: ReactNode;
}

/** Conditionally renders content using the application's permission adapter. */
export function ApplicationCan({ permission, children, fallback = null }: ApplicationCanProps) {
  const canAccess = useApplicationCanAccess();
  return <>{canAccess(permission) ? children : fallback}</>;
}
