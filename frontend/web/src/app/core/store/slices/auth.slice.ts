// src/app/core/store/slices/auth.slice.ts
import {
  getSessionApiAuthSessionGet,
  loginApiAuthLoginPost,
  logoutApiAuthLogoutPost,
} from '@shared/api/generated/services.gen';
import { StateCreator } from 'zustand';
import { getPermissionsForRoles, normalizeRoles } from '../../auth/permissions';
import { User, UserPermissions } from '../../auth/types';
import { clearPrivateQueryData } from '../../queryClient';

const normalizeAuthType = (authType?: string | null): 'session' | 'api_key' | null => {
  if (authType === 'session' || authType === 'api_key') return authType;
  return null;
};

export interface AuthState {
  user: User | null;
  authType: 'session' | 'api_key' | null;
  isAuthenticated: boolean;
  isLoading: boolean;

  login: (username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  bootstrapSession: () => Promise<void>;
}

type AuthSliceRootState = AuthState & { permissions: UserPermissions };

export const createAuthSlice: StateCreator<AuthSliceRootState, [], [], AuthState> = (set) => ({
  user: null,
  authType: null,
  isAuthenticated: false,
  isLoading: false,

  login: async (username: string, password: string) => {
    clearPrivateQueryData();
    set({ isLoading: true });
    try {
      const data = await loginApiAuthLoginPost({
        requestBody: {
          username,
          password,
        },
      });

      const responseUser = data.user;
      const user: User | null = responseUser
        ? {
          id: responseUser.id,
          name: responseUser.name,
          email: responseUser.email,
          roles: normalizeRoles(responseUser.roles),
          permissions: getPermissionsForRoles(responseUser.roles),
        }
        : null;

      set({
        user,
        permissions: user?.permissions || [],
        authType: normalizeAuthType(data.auth_type),
        isAuthenticated: data.is_authenticated,
        isLoading: false,
      });
    } catch (error) {
      set({ user: null, permissions: [], authType: null, isAuthenticated: false, isLoading: false });
      throw error;
    }
  },

  logout: async () => {
    clearPrivateQueryData();
    try {
      await logoutApiAuthLogoutPost();
    } finally {
      clearPrivateQueryData();
      set({ user: null, permissions: [], authType: null, isAuthenticated: false });
    }
  },

  bootstrapSession: async () => {
    set({ isLoading: true });
    try {
      const data = await getSessionApiAuthSessionGet();
      const responseUser = data.user;
      const user: User | null = responseUser
        ? {
          id: responseUser.id,
          name: responseUser.name,
          email: responseUser.email,
          roles: normalizeRoles(responseUser.roles),
          permissions: getPermissionsForRoles(responseUser.roles),
        }
        : null;

      set({
        user,
        permissions: user?.permissions || [],
        authType: normalizeAuthType(data.auth_type),
        isAuthenticated: data.is_authenticated,
        isLoading: false,
      });
    } catch {
      set({ user: null, permissions: [], authType: null, isAuthenticated: false, isLoading: false });
    }
  },
});
