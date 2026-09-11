import type { AppShellUser } from '../user/UserMenu';
import type { PermissionRequirement } from '../plugin';

export interface ApplicationAuthState {
  user?: AppShellUser | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  bootstrapSession?: () => Promise<void>;
}

/**
 * Application-owned authentication bridge.
 *
 * The shell deliberately does not know how authentication state is stored
 * (Zustand, Redux, React context, an external SDK, etc.). The application
 * exposes the state/actions the shell needs through this hook contract.
 */
export interface AuthAdapter {
  useAuthState: () => ApplicationAuthState;
}

export type CanAccess = (permission: PermissionRequirement) => boolean;

/**
 * Application-owned permission bridge.
 *
 * Permission resources/actions remain application policy. The shell only asks
 * whether a declarative PermissionRequirement is allowed.
 */
export interface PermissionAdapter {
  useCanAccess: () => CanAccess;
}

export interface ApplicationRuntimeAdapters {
  auth?: AuthAdapter;
  permissions?: PermissionAdapter;
}
