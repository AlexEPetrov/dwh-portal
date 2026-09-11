import '@asset-management/ui-kit/styles.css';
import '../styles.css';
import type { QueryClient } from '@tanstack/react-query';
import type { ThemeConfig } from 'antd';
import { StrictMode, type ComponentProps } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { RouterProvider } from 'react-router-dom';
import { ApplicationProviders } from '../providers/ApplicationProviders';
import { ApplicationRuntimeProvider, type ApplicationRuntimeAdapters } from '../runtime';

type ProviderLocale = ComponentProps<typeof ApplicationProviders>['locale'];
type Router = ComponentProps<typeof RouterProvider>['router'];

export interface RenderApplicationOptions {
  root: HTMLElement;
  router: Router;
  locale?: ProviderLocale;
  theme?: ThemeConfig;
  queryClient?: QueryClient;
  strictMode?: boolean;
  runtime?: ApplicationRuntimeAdapters;
}

export function renderApplication({
  root,
  router,
  locale,
  theme,
  queryClient,
  strictMode = true,
  runtime,
}: RenderApplicationOptions): Root {
  const application = (
    <ApplicationProviders locale={locale} theme={theme} queryClient={queryClient}>
      <ApplicationRuntimeProvider auth={runtime?.auth} permissions={runtime?.permissions}>
        <RouterProvider router={router} />
      </ApplicationRuntimeProvider>
    </ApplicationProviders>
  );

  const reactRoot = createRoot(root);
  reactRoot.render(strictMode ? <StrictMode>{application}</StrictMode> : application);
  return reactRoot;
}
