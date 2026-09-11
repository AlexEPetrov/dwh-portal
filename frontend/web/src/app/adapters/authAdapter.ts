import type { AuthAdapter } from '@asset-management/app-shell/runtime';
import { useStore } from '@app/core';

/**
 * Bridges the application's current auth implementation to app-shell.
 * Zustand and backend-specific auth details intentionally remain in web.
 */
export const authAdapter: AuthAdapter = {
  useAuthState() {
    const user = useStore((state) => state.user);
    const isAuthenticated = useStore((state) => state.isAuthenticated);
    const isLoading = useStore((state) => state.isLoading);
    const login = useStore((state) => state.login);
    const logout = useStore((state) => state.logout);
    const bootstrapSession = useStore((state) => state.bootstrapSession);

    return {
      user,
      isAuthenticated,
      isLoading,
      login,
      logout,
      bootstrapSession,
    };
  },
};
