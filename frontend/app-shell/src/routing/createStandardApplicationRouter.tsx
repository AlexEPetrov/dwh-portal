import type { ReactElement } from 'react';
import type { RouteObject } from 'react-router-dom';
import { ApplicationAuthBoundary, ApplicationLoginPage } from '../auth';
import type { ApplicationAuthBoundaryProps, ApplicationLoginPageProps } from '../auth';
import { ApplicationLayout, type ApplicationLayoutProps } from '../layout';
import { createApplicationRouter } from './createApplicationRouter';

export interface CreateStandardApplicationRouterOptions {
  loginPath?: string;
  homeElement: ReactElement;
  routes: RouteObject[];
  layout: ApplicationLayoutProps;
  login?: ApplicationLoginPageProps;
  auth?: Omit<ApplicationAuthBoundaryProps, 'loginPath'>;
}

/**
 * Builds the standard shell route tree from application metadata.
 * Auth, layout, sidebar and user-menu mechanics stay inside app-shell.
 */
export function createStandardApplicationRouter({
  loginPath = '/login',
  homeElement,
  routes,
  layout,
  login,
  auth,
}: CreateStandardApplicationRouterOptions) {
  return createApplicationRouter({
    loginPath,
    loginElement: <ApplicationLoginPage {...login} />,
    authElement: <ApplicationAuthBoundary {...auth} loginPath={loginPath} />,
    layoutElement: <ApplicationLayout {...layout} />,
    homeElement,
    routes,
  });
}
