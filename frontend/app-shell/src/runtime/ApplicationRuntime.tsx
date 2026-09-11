import { createContext, useContext, type ReactNode } from 'react';
import type {
  ApplicationAuthState,
  ApplicationRuntimeAdapters,
  AuthAdapter,
  CanAccess,
  PermissionAdapter,
} from './types';

const AuthStateContext = createContext<ApplicationAuthState | undefined>(undefined);
const PermissionAccessContext = createContext<CanAccess | undefined>(undefined);

interface AdapterBridgeProps<TAdapter> {
  adapter: TAdapter;
  children: ReactNode;
}

function AuthAdapterBridge({ adapter, children }: AdapterBridgeProps<AuthAdapter>) {
  const authState = adapter.useAuthState();
  return <AuthStateContext.Provider value={authState}>{children}</AuthStateContext.Provider>;
}

function PermissionAdapterBridge({ adapter, children }: AdapterBridgeProps<PermissionAdapter>) {
  const canAccess = adapter.useCanAccess();
  return <PermissionAccessContext.Provider value={canAccess}>{children}</PermissionAccessContext.Provider>;
}

export interface ApplicationRuntimeProviderProps extends ApplicationRuntimeAdapters {
  children: ReactNode;
}

export function ApplicationRuntimeProvider({
  auth,
  permissions,
  children,
}: ApplicationRuntimeProviderProps) {
  let content = children;

  if (permissions) {
    content = <PermissionAdapterBridge adapter={permissions}>{content}</PermissionAdapterBridge>;
  }

  if (auth) {
    content = <AuthAdapterBridge adapter={auth}>{content}</AuthAdapterBridge>;
  }

  return <>{content}</>;
}

export function useApplicationAuth(): ApplicationAuthState {
  const authState = useContext(AuthStateContext);
  if (!authState) {
    throw new Error('Application auth adapter is not configured.');
  }
  return authState;
}

export function useApplicationCanAccess(): CanAccess {
  const canAccess = useContext(PermissionAccessContext);
  if (!canAccess) {
    throw new Error('Application permission adapter is not configured.');
  }
  return canAccess;
}

export function useOptionalApplicationCanAccess(): CanAccess | undefined {
  return useContext(PermissionAccessContext);
}
