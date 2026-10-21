import type { ModuleRegistration } from '@asset-management/app-shell/plugin';
import { RouteSuspense } from '@asset-management/app-shell/routing';
import { lazy, type ReactNode } from 'react';
import menu from './menu';

const ExtractionSourcesEditPage = lazy(() => import('./pages/ExtractionSourcesEditPage'));

const wrap = (el: ReactNode) => <RouteSuspense>{el}</RouteSuspense>;

const routes: ModuleRegistration['routes'] = () => [
  { path: '/admin/extraction-sources', element: wrap(<ExtractionSourcesEditPage />) },
];

export default {
  enabled: true,
  order: 40,
  menu,
  routes,
} satisfies ModuleRegistration;
