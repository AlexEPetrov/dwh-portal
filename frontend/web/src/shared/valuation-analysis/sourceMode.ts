import type { ObservationDateScenarioControlValue } from '@shared/ui/ObservationDateScenarioControl';
import type { SimulationCurrencyTarget } from '@shared/ui/SimulationCurrencyTargetSelector';
import type { ValuationPeriodMode, ValuationScopeFilterValue } from '@shared/ui/ValuationScopeFilter';
import dayjs from 'dayjs';

export type ValuationAnalysisSourceMode = 'filter' | 'balance';

export interface ValuationFilterRule {
    action: 'include' | 'exclude';
    market?: string[];
    product?: string[];
    supply_path?: string[];
    gl_account?: string[];
    scenario?: string[];
    period_from?: string;
    period_to?: string;
}

export interface ValuationAnalysisSourceState {
    sourceMode: ValuationAnalysisSourceMode;
    periodMode: ValuationPeriodMode | 'prices';
    target: SimulationCurrencyTarget;
    dateScenario: ObservationDateScenarioControlValue;
    balanceDateScenario: ObservationDateScenarioControlValue;
    selectedTreeSlug: string | undefined;
    scopeFilter: ValuationScopeFilterValue;
    filterRules?: ValuationFilterRule[];
}

export const BALANCE_SOURCE_PERIOD_MODE = 'payments' as const;
export const BALANCE_SOURCE_TARGET = 'value_rub' as const;
export const BALANCE_SOURCE_NOTICE = 'Balance mode uses payments year slice';

export const emptyDateScenario = (): ObservationDateScenarioControlValue => ({
    observationDate: '',
    scenario: null,
    valuationType: null,
});

export const defaultValuationAnalysisScopeFilter = (): ValuationScopeFilterValue => ({
    markets: [],
    products: [],
    supplyPaths: [],
    glAccounts: [],
    periodFrom: dayjs().startOf('year').format('YYYY-MM-DD'),
    periodTo: dayjs().endOf('year').format('YYYY-MM-DD'),
});

export const effectiveSourcePeriodMode = (sourceMode: ValuationAnalysisSourceMode, periodMode: ValuationAnalysisSourceState['periodMode']) => (
    sourceMode === 'balance' ? BALANCE_SOURCE_PERIOD_MODE : periodMode
);
