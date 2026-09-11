// src/shared/hooks/usePermission.ts
import { canPerform, type Action, type PermissionRule, useStore } from '@app/core';
import { useCallback } from 'react';

/**
 * Хук для проверки разрешений текущего пользователя.
 */
export function usePermission() {
  const permissions = useStore((state) => state.permissions);

  const can = useCallback(
    (resource: string, action: Action, attrs?: Partial<PermissionRule['constraints']>) => {
      return canPerform(permissions, resource, action, attrs);
    },
    [permissions]
  );

  return { permissions, can };
}
