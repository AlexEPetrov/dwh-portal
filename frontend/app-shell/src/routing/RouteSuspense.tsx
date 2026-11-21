import { Component, Suspense, type ReactNode } from 'react';
import { useLocation } from 'react-router-dom';

export interface RouteSuspenseProps {
  children: ReactNode;
  fallback?: ReactNode;
  errorFallback?: ReactNode;
}

const DEFAULT_FALLBACK = <div style={{ padding: 24, textAlign: 'center' }}>Загрузка...</div>;

const DEFAULT_ERROR_FALLBACK = (
  <div role="alert" style={{ padding: 24, textAlign: 'center' }}>
    <p>Не удалось открыть страницу.</p>
    <button type="button" onClick={() => window.location.reload()}>Перезагрузить приложение</button>
  </div>
);

class PageErrorBoundary extends Component<
  { children: ReactNode; fallback: ReactNode },
  { failed: boolean }
> {
  state = { failed: false };

  static getDerivedStateFromError() {
    return { failed: true };
  }

  render() {
    return this.state.failed ? this.props.fallback : this.props.children;
  }
}

/** Isolates lazy import/render failures while leaving the application chrome usable. */
export function RouteSuspense({
  children,
  fallback = DEFAULT_FALLBACK,
  errorFallback = DEFAULT_ERROR_FALLBACK,
}: RouteSuspenseProps) {
  const location = useLocation();
  return (
    <PageErrorBoundary key={location.pathname} fallback={errorFallback}>
      <Suspense fallback={fallback}>{children}</Suspense>
    </PageErrorBoundary>
  );
}
