// src/app/core/index.ts

// Store
export { useStore } from './store'; // было './store.ts', стало './store'
export type { RootState } from './store/types';

// API
export { apiClient } from './api';

// Auth & Permissions
export * from './auth/permissions';
export type { Action, AppRole, PermissionRule, User, UserPermissions } from './auth/types';
