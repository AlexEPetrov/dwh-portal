import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ConfigProvider, type ThemeConfig } from 'antd';
import type { ComponentProps, ReactNode } from 'react';
import { ThemeModeProvider } from '../theme/ThemeModeProvider';

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
  theme,
  queryClient = defaultQueryClient,
}: ApplicationProvidersProps) {
  return (
    <ConfigProvider locale={locale}>
      <QueryClientProvider client={queryClient}>
        <ThemeModeProvider theme={theme}>{children}</ThemeModeProvider>
      </QueryClientProvider>
    </ConfigProvider>
  );
}
