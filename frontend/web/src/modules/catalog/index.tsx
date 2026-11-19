import type { ModuleRegistration } from '@asset-management/app-shell/plugin';
import { RouteSuspense } from '@asset-management/app-shell/routing';
import { lazy, type ReactNode } from 'react';
import menu from './menu';

const OverviewPage = lazy(() => import('./pages/OverviewPage'));
const ObjectsPage = lazy(() => import('./pages/ObjectsPage'));
const ObjectDetailPage = lazy(() => import('./pages/ObjectDetailPage'));
const StoragePage = lazy(() => import('./pages/StoragePage'));
const LineagePage = lazy(() => import('./pages/LineagePage'));
const LineageUniversePage = lazy(() => import('./pages/LineageUniversePage'));
const ChangesPage = lazy(() => import('./pages/ChangesPage'));

/** Public catalog landing page; consumers need not import catalog internals. */
export function CatalogHomePage() {
  return <RouteSuspense><OverviewPage /></RouteSuspense>;
}

const wrap = (el: ReactNode) => <RouteSuspense>{el}</RouteSuspense>;

const routes: ModuleRegistration['routes'] = () => [
  { path: '/overview', element: wrap(<OverviewPage />) },
  { path: '/objects', element: wrap(<ObjectsPage />) },
  { path: '/objects/:assetId', element: wrap(<ObjectDetailPage />) },
  { path: '/storage', element: wrap(<StoragePage />) },
  { path: '/lineage', element: wrap(<LineagePage />) },
  { path: '/lineage/universe', element: wrap(<LineageUniversePage />) },
  { path: '/lineage/universe/:assetId', element: wrap(<LineageUniversePage />) },
  { path: '/lineage/:assetId', element: wrap(<LineagePage />) },
  { path: '/changes', element: wrap(<ChangesPage />) },
];

export default {
  id: 'catalog',
  enabled: true,
  order: 20,
  menu,
  routes,
} satisfies ModuleRegistration;
