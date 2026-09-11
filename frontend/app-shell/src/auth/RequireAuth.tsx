import { Spin } from 'antd';
import { useEffect, useState } from 'react';
import { Navigate, Outlet, useLocation } from 'react-router-dom';

export interface RequireAuthProps {
  isAuthenticated: boolean;
  isLoading: boolean;
  bootstrapSession?: () => Promise<void>;
  loginPath?: string;
}

export function RequireAuth({
  isAuthenticated,
  isLoading,
  bootstrapSession,
  loginPath = '/login',
}: RequireAuthProps) {
  const location = useLocation();
  const [isSessionChecked, setIsSessionChecked] = useState(false);

  useEffect(() => {
    let isMounted = true;

    const runBootstrap = async () => {
      try {
        await bootstrapSession?.();
      } finally {
        if (isMounted) {
          setIsSessionChecked(true);
        }
      }
    };

    void runBootstrap();

    return () => {
      isMounted = false;
    };
  }, [bootstrapSession]);

  if (!isSessionChecked || isLoading) {
    return (
      <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <Spin size="large" />
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to={loginPath} replace state={{ from: location }} />;
  }

  return <Outlet />;
}
