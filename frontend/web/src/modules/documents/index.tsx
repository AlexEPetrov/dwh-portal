import type { ModuleRegistration } from '@asset-management/app-shell/plugin';
import { RouteSuspense } from '@asset-management/app-shell/routing';
import { lazy, type ReactNode } from 'react';
import menu from './menu';

const DocumentUploadPage = lazy(() => import('./pages/DocumentUploadPage'));

const wrap = (el: ReactNode) => <RouteSuspense>{el}</RouteSuspense>;

const routes: ModuleRegistration['routes'] = () => [
  { path: '/documents/upload', element: wrap(<DocumentUploadPage />) },
];

export default {
  id: 'documents',
  enabled: true,
  order: 30,
  menu,
  routes,
} satisfies ModuleRegistration;
