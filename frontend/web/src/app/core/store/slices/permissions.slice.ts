// src/app/core/store/slices/permissions.slice.ts
import { StateCreator } from 'zustand';
import { UserPermissions } from '../../auth/types';

export interface PermissionsState {
  permissions: UserPermissions;
  setPermissions: (permissions: UserPermissions) => void;
}

export const createPermissionsSlice: StateCreator<PermissionsState> = (set) => ({
  permissions: [],
  setPermissions: (permissions) => set({ permissions }),
});
