import { loadDictionaryByName } from '@shared/api/dictionaries';
import {
    getAvailableValuationTypesApiValuationResultsValuationTypesGet,
    getObservationDatesApiValuationResultsObservationDatesGet,
} from '@shared/api/generated/services.gen';
import type { ObservationDateScenarioControlValue } from '@shared/ui/ObservationDateScenarioControl';

export interface SimulationDateScenarioBootstrapApi {
    getObservationDates: typeof getObservationDatesApiValuationResultsObservationDatesGet;
    getValuationTypes: typeof getAvailableValuationTypesApiValuationResultsValuationTypesGet;
}

const defaultApi: SimulationDateScenarioBootstrapApi = {
    getObservationDates: getObservationDatesApiValuationResultsObservationDatesGet,
    getValuationTypes: getAvailableValuationTypesApiValuationResultsValuationTypesGet,
};

/**
 * Resolve the default filter-mode date scenario for page bootstrap:
 * latest simulation observation date + first available valuation type + 'default' scenario.
 *
 * Used when no saved balance exists so the page does not depend on
 * ObservationDateScenarioControl self-init racing with the bootstrap updateFilters call.
 * Returns null when no simulation observation dates are available.
 */
export const resolveLatestSimulationDateScenario = async (
    api: SimulationDateScenarioBootstrapApi = defaultApi,
): Promise<ObservationDateScenarioControlValue | null> => {
    const response = await api.getObservationDates();
    const dates = [...new Set((response.observation_dates || []).map((item) => item.date).filter(Boolean))]
        .sort((a, b) => b.localeCompare(a));
    const observationDate = dates[0];
    if (!observationDate) return null;

    let valuationType: string | null = null;
    try {
        const valuationTypesResponse = await api.getValuationTypes({ observationDate, runMode: 'simulation' });
        valuationType = (valuationTypesResponse.valuation_types || [])
            .map((item) => item.type)
            .filter(Boolean)[0] ?? null;
    } catch {
        valuationType = null;
    }

    let scenario: string | null = null;
    try {
        const scenarioOptions = await loadDictionaryByName('scenarios');
        if (scenarioOptions.some((option) => option.value === 'default')) {
            scenario = 'default';
        }
    } catch {
        scenario = null;
    }

    return { observationDate, valuationType, scenario };
};
