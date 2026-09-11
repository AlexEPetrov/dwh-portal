// src/app/core/auth/types.ts

export type AppRole = 'admin' | 'viewer';

export type Action = 'read' | 'create' | 'edit' | 'delete' | 'export' | 'run' | 'download' | 'view' | 'history' | '*';

export interface PermissionRule {
  resource: string;
  action: Action | Action[];
  constraints?: {
    categories?: string[];
    markets?: string[];
    regions?: string[];
    counterparties?: string[];
  };
}

export type UserPermissions = PermissionRule[];

export interface User {
  id: string;
  name: string;
  email: string;
  roles?: AppRole[];
  permissions: UserPermissions;
}
