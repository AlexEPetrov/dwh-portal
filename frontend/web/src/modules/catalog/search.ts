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
