import type {
    LineageResponse,
    LineageRootsResponse,
    ListAssetsData,
    ListChangesData,
} from '@shared/api/generated';
import {
    getAsset,
    getAssetColumns,
    getAssetLineage,
    getOverview,
    getStorage,
    getStorageHistory,
    listAssetLoads,
    listAssets,
    listChanges,
    listLineageRoots,
} from '@shared/api/generated';
import type { CancelablePromise } from '@shared/api/generated/core/CancelablePromise';
import { useQueries, useQuery } from '@tanstack/react-query';

/** Consume Query's signal and cancel the generated transport, not just its observer. */
async function requestWithSignal<T>(signal: AbortSignal, request: CancelablePromise<T>): Promise<T> {
    const cancel = () => request.cancel();
    signal.addEventListener('abort', cancel, { once: true });
    if (signal.aborted) cancel();
    try {
        return await request;
    } finally {
        signal.removeEventListener('abort', cancel);
    }
}

// Snapshot freshness belongs to API responses, not a client-side fresh-data window.
// Never inherit app-level previous-data placeholders across assets/filters/pages.
const lifecycle = { staleTime: 0, placeholderData: () => undefined } as const;

const catalogScope = ['portal', 'catalog'] as const;
export const catalogKeys = {
    all: catalogScope,
    overview: [...catalogScope, 'overview'] as const,
    storage: [...catalogScope, 'storage'] as const,
    storageHistory: [...catalogScope, 'storage', 'history'] as const,
    assets: (params: ListAssetsData) => [...catalogScope, 'assets', params] as const,
    asset: (assetId: string | undefined) => [...catalogScope, 'asset', assetId] as const,
    columns: (assetId: string | undefined) => [...catalogScope, 'columns', assetId] as const,
    lineage: (assetId: string | undefined) =>
        assetId ? [...catalogScope, 'lineage', 'asset', assetId] as const : [...catalogScope, 'lineage', 'roots'] as const,
    changes: (params: ListChangesData) => [...catalogScope, 'changes', params] as const,
    periodChanges: (days: number) => [...catalogScope, 'changes', 'period', days] as const,
    loads: (assetId: string, page: number, pageSize: number) =>
        [...catalogScope, 'loads', assetId, { page, pageSize, includeTotal: false }] as const,
};

export const useCatalogOverview = () => useQuery({
    ...lifecycle,
    queryKey: catalogKeys.overview,
    queryFn: ({ signal }) => requestWithSignal(signal, getOverview()),
});

export const useCatalogStorage = () => useQuery({
    ...lifecycle,
    queryKey: catalogKeys.storage,
    queryFn: ({ signal }) => requestWithSignal(signal, getStorage()),
});

export const useCatalogStorageHistory = () => useQuery({
    ...lifecycle,
    queryKey: catalogKeys.storageHistory,
    queryFn: ({ signal }) => requestWithSignal(signal, getStorageHistory()),
});

export const useCatalogAssets = (params: ListAssetsData, enabled = true) => useQuery({
    ...lifecycle,
    enabled,
    queryKey: catalogKeys.assets(params),
    queryFn: ({ signal }) => requestWithSignal(signal, listAssets(params)),
});

export const useCatalogAsset = (assetId: string | undefined) => useQuery({
    ...lifecycle,
    queryKey: catalogKeys.asset(assetId),
    enabled: Boolean(assetId),
    queryFn: ({ signal }) => {
        if (!assetId) throw new Error('Asset identifier is required');
        return requestWithSignal(signal, getAsset({ assetId }));
    },
});

export const useCatalogColumns = (assetId: string | undefined) => useQuery({
    ...lifecycle,
    queryKey: catalogKeys.columns(assetId),
    enabled: Boolean(assetId),
    queryFn: ({ signal }) => {
        if (!assetId) throw new Error('Asset identifier is required');
        return requestWithSignal(signal, getAssetColumns({ assetId }));
    },
});

export const useCatalogLineage = (assetId?: string, enabled = true) => useQuery<LineageResponse | LineageRootsResponse>({
    ...lifecycle,
    queryKey: catalogKeys.lineage(assetId),
    enabled,
    queryFn: ({ signal }) => assetId
        ? requestWithSignal(signal, getAssetLineage({ assetId }))
        : requestWithSignal(signal, listLineageRoots()),
});

export const useCatalogChanges = (params: ListChangesData, enabled = true) => useQuery({
    ...lifecycle,
    queryKey: catalogKeys.changes(params),
    enabled,
    queryFn: ({ signal }) => requestWithSignal(signal, listChanges(params)),
});

export const useCatalogPeriodChanges = (days: number) => useQuery({
    ...lifecycle,
    queryKey: catalogKeys.periodChanges(days),
    queryFn: ({ signal }) => {
        // Recompute on every refetch without putting a render-time clock in the key.
        const since = new Date();
        since.setUTCDate(since.getUTCDate() - days);
        return requestWithSignal(signal, listChanges({ since: since.toISOString(), pageSize: 200 }));
    },
});

export const useCatalogLoads = (assetId: string, page: number, pageSize: number) => useQuery({
    ...lifecycle,
    queryKey: catalogKeys.loads(assetId, page, pageSize),
    enabled: Boolean(assetId),
    queryFn: ({ signal }) => requestWithSignal(signal, listAssetLoads({ assetId, page, pageSize, includeTotal: false })),
});

export const LINEAGE_PICKER_TYPES = [
    'DATA_SOURCE', 'EXTRACTION_SOURCE', 'PROCESS', 'TABLE', 'VIEW', 'STORAGE_LOCATION',
] as const;

export const useCatalogLineagePicker = () => useQueries({
    queries: LINEAGE_PICKER_TYPES.map((type) => {
        const params: ListAssetsData = { type, status: 'active', pageSize: 100 };
        return {
            ...lifecycle,
            queryKey: catalogKeys.assets(params),
            queryFn: ({ signal }: { signal: AbortSignal }) => requestWithSignal(signal, listAssets(params)),
        };
    }),
});
