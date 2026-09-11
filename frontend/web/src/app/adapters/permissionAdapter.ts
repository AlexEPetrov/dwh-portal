import type { PermissionAdapter } from '@asset-management/app-shell/runtime';
import { canPerform, type Action, type PermissionRule, useStore } from '@app/core';
import { useCallback } from 'react';

/**
 * Bridges declarative shell/plugin permission requirements to the application's
 * concrete ATRM permission model. app-shell does not know Action, canPerform,
 * UserPermissions, or how those permissions are stored.
 */
export const permissionAdapter: PermissionAdapter = {
  useCanAccess() {
    const permissions = useStore((state) => state.permissions);

    return useCallback(
      (permission) =>
        canPerform(
          permissions,
          permission.resource,
          permission.action as Action,
          permission.context as Partial<PermissionRule['constraints']> | undefined,
        ),
      [permissions],
    );
  },
};
