import type { ListAssetsData } from '@shared/api/generated';
import { updateCatalogFilters } from './navigation';

/** Limit suggestions, not the search scope: the server searches all active objects. */
export const overviewSearchParams = (query: string): ListAssetsData => ({
    q: query.trim() || undefined,
    status: 'active',
    sort: 'qualified_name',
    page: 1,
    pageSize: 20,
});

/** Carry the same query and lifecycle filter into the paginated results page. */
export const overviewSearchUrl = (query: string): string => {
    const params = updateCatalogFilters(new URLSearchParams(), {
        q: query.trim() || undefined,
        status: 'active',
    });
    return `/objects?${params}`;
};

/** A distinct action, never an object UUID; only offered for confirmed query matches. */
export const matchingResultsOption = (query: string, total: number | undefined, ready: boolean) =>
    ready && query.trim() && total !== undefined && total > 0
        ? [{
            value: '__matching_catalog_results__', kind: 'matches' as const,
            label: `Показать все подходящие (${total})`
        }]
        : [];
