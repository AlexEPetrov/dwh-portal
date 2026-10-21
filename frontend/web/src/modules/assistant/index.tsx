import type { ModuleRegistration } from '@asset-management/app-shell/plugin';
import { RouteSuspense } from '@asset-management/app-shell/routing';
import { lazy, type ReactNode } from 'react';
import menu from './menu';

const AssistantPage = lazy(() => import('./pages/AssistantPage'));

const wrap = (el: ReactNode) => <RouteSuspense>{el}</RouteSuspense>;

const routes: ModuleRegistration['routes'] = () => [
  { path: '/assistant', element: wrap(<AssistantPage />) },
];

export default {
  enabled: true,
  order: 10,
  menu,
  routes,
} satisfies ModuleRegistration;
