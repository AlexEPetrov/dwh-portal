import {
    getAvailableValuationTypesApiValuationResultsValuationTypesGet,
    getObservationDatesApiValuationResultsObservationDatesGet,
    getSavedMetadataApiValuationGlCalculatedTreeSavedMetadataGet,
} from '@shared/api/generated/services.gen';
import type { BalanceTreeSaveMetadata } from '@shared/api/generated/types.gen';

export interface SavedBalanceBootstrapApi {
    getObservationDates: typeof getObservationDatesApiValuationResultsObservationDatesGet;
    getValuationTypes: typeof getAvailableValuationTypesApiValuationResultsValuationTypesGet;
    getSavedMetadata: typeof getSavedMetadataApiValuationGlCalculatedTreeSavedMetadataGet;
}

const defaultApi: SavedBalanceBootstrapApi = {
    getObservationDates: getObservationDatesApiValuationResultsObservationDatesGet,
    getValuationTypes: getAvailableValuationTypesApiValuationResultsValuationTypesGet,
    getSavedMetadata: getSavedMetadataApiValuationGlCalculatedTreeSavedMetadataGet,
};

const newestFirst = (left: BalanceTreeSaveMetadata, right: BalanceTreeSaveMetadata) => {
    const yearDifference = right.valuation_year - left.valuation_year;
    return yearDifference || String(right.saved_at).localeCompare(String(left.saved_at));
};

export const loadSavedBalancesForDate = async (
    observationDate: string,
    api: SavedBalanceBootstrapApi = defaultApi,
): Promise<BalanceTreeSaveMetadata[]> => {
    const valuationTypesResponse = await api.getValuationTypes({ observationDate, runMode: 'static' });
    const valuationTypes = [...new Set((valuationTypesResponse.valuation_types || []).map((item) => item.type).filter(Boolean))];
    const coverage = await Promise.all(valuationTypes.map((valuationType) => (
        api.getSavedMetadata({ observationDate, valuationType })
    )));
    return coverage.flatMap((item) => item.items || []).sort(newestFirst);
};

export const resolveLatestSavedBalance = async (
    api: SavedBalanceBootstrapApi = defaultApi,
): Promise<BalanceTreeSaveMetadata | null> => {
    const response = await api.getObservationDates();
    const dates = [...new Set((response.observation_dates || []).map((item) => item.date))].sort((a, b) => b.localeCompare(a));
    for (const observationDate of dates) {
        const balances = await loadSavedBalancesForDate(observationDate, api);
        if (balances.length > 0) return balances[0];
    }
    return null;
};

export const validateSavedBalanceReference = async (
    observationDate: string,
    valuationType: string,
    balanceTreeSlug: string,
    api: SavedBalanceBootstrapApi = defaultApi,
): Promise<boolean> => {
    return Boolean(await resolveSavedBalanceReference(observationDate, valuationType, balanceTreeSlug, api));
};

export const resolveSavedBalanceReference = async (
    observationDate: string,
    valuationType: string,
    balanceTreeSlug: string,
    api: SavedBalanceBootstrapApi = defaultApi,
): Promise<BalanceTreeSaveMetadata | null> => {
    const items = await loadSavedBalancesForDate(observationDate, api);
    return items.find((item) => item.valuation_type === valuationType && item.balance_tree_slug === balanceTreeSlug) || null;
};

export const savedBalancePeriod = (metadata: BalanceTreeSaveMetadata) => ({
    periodFrom: `${metadata.valuation_year}-01-01`,
    periodTo: `${metadata.valuation_year}-12-31`,
});
