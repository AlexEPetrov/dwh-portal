import { Suspense, type ReactNode } from 'react';

export interface RouteSuspenseProps {
  children: ReactNode;
  fallback?: ReactNode;
}

const DEFAULT_FALLBACK = <div style={{ padding: 24, textAlign: 'center' }}>Загрузка...</div>;

/** Standard suspense boundary for lazy application routes. */
export function RouteSuspense({ children, fallback = DEFAULT_FALLBACK }: RouteSuspenseProps) {
  return <Suspense fallback={fallback}>{children}</Suspense>;
}
