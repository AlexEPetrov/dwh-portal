import { useApplicationAuth } from '../runtime';
import { RequireAuth, type RequireAuthProps } from './RequireAuth';

export type ApplicationAuthBoundaryProps = Omit<
  RequireAuthProps,
  'isAuthenticated' | 'isLoading' | 'bootstrapSession'
>;

export function ApplicationAuthBoundary(props: ApplicationAuthBoundaryProps) {
  const { isAuthenticated, isLoading, bootstrapSession } = useApplicationAuth();
  return (
    <RequireAuth
      {...props}
      isAuthenticated={isAuthenticated}
      isLoading={isLoading}
      bootstrapSession={bootstrapSession}
    />
  );
}
