import type { ModuleRegistration } from '@asset-management/app-shell/plugin';
import { RouteSuspense } from '@asset-management/app-shell/routing';
import { lazy, type ReactNode } from 'react';
import menu from './menu';

const OverviewPage = lazy(() => import('./pages/OverviewPage'));
const ObjectsPage = lazy(() => import('./pages/ObjectsPage'));
const ObjectDetailPage = lazy(() => import('./pages/ObjectDetailPage'));
const StoragePage = lazy(() => import('./pages/StoragePage'));
const LineagePage = lazy(() => import('./pages/LineagePage'));
const ChangesPage = lazy(() => import('./pages/ChangesPage'));
const DocumentUploadPage = lazy(() => import('./pages/DocumentUploadPage'));
const ExtractionSourcesEditPage = lazy(() => import('./pages/ExtractionSourcesEditPage'));
const AssistantPage = lazy(() => import('./pages/AssistantPage'));

const wrap = (el: ReactNode) => <RouteSuspense>{el}</RouteSuspense>;

const routes: ModuleRegistration['routes'] = () => [
  { path: '/overview', element: wrap(<OverviewPage />) },
  { path: '/objects', element: wrap(<ObjectsPage />) },
  { path: '/objects/:assetId', element: wrap(<ObjectDetailPage />) },
  { path: '/storage', element: wrap(<StoragePage />) },
  { path: '/lineage', element: wrap(<LineagePage />) },
  { path: '/lineage/:assetId', element: wrap(<LineagePage />) },
  { path: '/changes', element: wrap(<ChangesPage />) },
  { path: '/documents/upload', element: wrap(<DocumentUploadPage />) },
  { path: '/admin/extraction-sources', element: wrap(<ExtractionSourcesEditPage />) },
  { path: '/assistant', element: wrap(<AssistantPage />) },
];

export default {
  enabled: true,
  menu,
  routes,
} satisfies ModuleRegistration;
