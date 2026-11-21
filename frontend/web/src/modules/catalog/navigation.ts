import type { ListAssetsData } from '@shared/api/generated';

/** Browser URL state for existing catalog filters, never an alternate API model. */
export type CatalogFilters = Pick<
    ListAssetsData, 'q' | 'database' | 'schema' | 'type' | 'source' | 'status' | 'changedSince' | 'sort'
>;

/** Restore server-authored list links using the generated API's existing fields. */
export const readCatalogFilters = (params: URLSearchParams): CatalogFilters => ({
    q: params.get('q') ?? undefined,
    database: params.get('database') ?? undefined,
    schema: params.get('schema') ?? undefined,
    type: params.get('type') ?? undefined,
    source: params.get('source') ?? undefined,
    status: params.get('status') === 'deleted' ? 'deleted' : 'active',
    changedSince: params.get('changed_since') ?? undefined,
    sort: 'qualified_name',
});

/** Keep sibling/unknown URL state; changing a filter starts at the first page. */
export const updateCatalogFilters = (
    current: URLSearchParams,
    updates: Partial<CatalogFilters>,
): URLSearchParams => {
    const next = new URLSearchParams(current);
    for (const [key, value] of Object.entries(updates)) {
        const parameter = key === 'changedSince' ? 'changed_since' : key;
        if (value === undefined || value === null || value === '') next.delete(parameter);
        else next.set(parameter, String(value));
    }
    next.delete('page');
    return next;
};
