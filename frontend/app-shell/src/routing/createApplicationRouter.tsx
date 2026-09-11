import { createBrowserRouter, type RouteObject } from 'react-router-dom';
import type { ReactElement } from 'react';

export interface CreateApplicationRouterOptions {
  loginPath?: string;
  loginElement: ReactElement;
  authElement: ReactElement;
  layoutElement: ReactElement;
  homeElement: ReactElement;
  routes: RouteObject[];
}

export function createApplicationRouter({
  loginPath = '/login',
  loginElement,
  authElement,
  layoutElement,
  homeElement,
  routes,
}: CreateApplicationRouterOptions) {
  return createBrowserRouter([
    {
      path: loginPath,
      element: loginElement,
    },
    {
      element: authElement,
      children: [
        {
          path: '/',
          element: layoutElement,
          children: [
            { index: true, element: homeElement },
            ...routes,
          ],
        },
      ],
    },
  ]);
}
