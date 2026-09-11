import { appTheme } from '@asset-management/ui-kit/theme';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ConfigProvider, type ThemeConfig } from 'antd';
import type { ComponentProps, ReactNode } from 'react';

const defaultQueryClient = new QueryClient();

export interface ApplicationProvidersProps {
  children: ReactNode;
  locale?: ComponentProps<typeof ConfigProvider>['locale'];
  theme?: ThemeConfig;
  queryClient?: QueryClient;
}

export function ApplicationProviders({
  children,
  locale,
  theme = appTheme,
  queryClient = defaultQueryClient,
}: ApplicationProvidersProps) {
  return (
    <ConfigProvider locale={locale}>
      <QueryClientProvider client={queryClient}>
        <ConfigProvider theme={theme}>{children}</ConfigProvider>
      </QueryClientProvider>
    </ConfigProvider>
  );
}
