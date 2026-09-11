import { currencyFromSimulationTarget } from '@shared/ui/SimulationCurrencyTargetSelector';
import {
    BALANCE_SOURCE_PERIOD_MODE,
    BALANCE_SOURCE_TARGET,
    effectiveSourcePeriodMode,
    type ValuationAnalysisSourceState,
} from './sourceMode';

export interface SimulationCombinedSourceParams {
    observationDate: string;
    periodStart: string;
    periodEnd: string;
    periodMode: 'valuations' | 'payments' | 'prices';
    target: 'value_rub' | 'value_usd' | 'price_rub' | 'price_usd';
    glAccounts?: string[];
    markets?: string[];
    products?: string[];
    supplyPaths?: string[];
    filters?: Record<string, string>;
    filterRules?: Record<string, unknown>[];
    sourceMode?: 'filter' | 'balance';
    balanceTreeSlug?: string;
    valuationType?: string | null;
    monthlyMode?: 'monthly_net_cash_flow' | 'cumulative_cash_position';
}

export interface ScenarioAnalysisSourceParams {
    mode: 'filter' | 'balance';
    markets?: string[];
    products?: string[];
    supplyPaths?: string[];
    glAccounts?: string[];
    periodMode?: 'valuations' | 'payments';
    currency?: 'rub' | 'usd';
    valuationType?: string | null;
    periodFrom?: string;
    periodTo?: string;
    balanceTreeSlug?: string;
    observationDate: string;
    scenario: string | null;
    filterRules?: Record<string, unknown>[];
}

const nonEmpty = (values: string[] | undefined) => (values && values.length > 0 ? values : undefined);

export const buildSimulationCombinedSourceParams = (state: ValuationAnalysisSourceState): SimulationCombinedSourceParams => {
    if (state.sourceMode === 'balance') {
        return {
            observationDate: state.balanceDateScenario.observationDate,
            periodStart: state.scopeFilter.periodFrom,
            periodEnd: state.scopeFilter.periodTo,
            periodMode: BALANCE_SOURCE_PERIOD_MODE,
            target: BALANCE_SOURCE_TARGET,
            sourceMode: 'balance',
            balanceTreeSlug: state.selectedTreeSlug,
            valuationType: state.balanceDateScenario.valuationType,
            filters: state.balanceDateScenario.scenario ? { scenario: state.balanceDateScenario.scenario } : undefined,
            filterRules: state.filterRules?.length ? state.filterRules as unknown as Record<string, unknown>[] : undefined,
        };
    }

    const filters: Record<string, string> = {};
    if (nonEmpty(state.scopeFilter.markets)) filters.market = state.scopeFilter.markets.join(',');
    if (nonEmpty(state.scopeFilter.products)) filters.product = state.scopeFilter.products.join(',');
    if (nonEmpty(state.scopeFilter.supplyPaths)) filters.supply_path = state.scopeFilter.supplyPaths.join(',');
    if (nonEmpty(state.scopeFilter.glAccounts)) filters.gl_account = state.scopeFilter.glAccounts.join(',');
    if (state.dateScenario.scenario) filters.scenario = state.dateScenario.scenario;

    const periodMode = effectiveSourcePeriodMode(state.sourceMode, state.periodMode);
    const target = periodMode === 'prices'
        ? state.target
        : (state.target.replace('price_', 'value_') as 'value_rub' | 'value_usd');

    return {
        observationDate: state.dateScenario.observationDate,
        periodStart: state.scopeFilter.periodFrom,
        periodEnd: state.scopeFilter.periodTo,
        periodMode,
        target,
        glAccounts: nonEmpty(state.scopeFilter.glAccounts),
        markets: nonEmpty(state.scopeFilter.markets),
        products: nonEmpty(state.scopeFilter.products),
        supplyPaths: nonEmpty(state.scopeFilter.supplyPaths),
        filters: Object.keys(filters).length > 0 ? filters : undefined,
        filterRules: state.filterRules?.length ? state.filterRules as unknown as Record<string, unknown>[] : undefined,
        sourceMode: 'filter',
        valuationType: state.dateScenario.valuationType,
    };
};

export const buildScenarioAnalysisSourceParams = (state: ValuationAnalysisSourceState): ScenarioAnalysisSourceParams => {
    if (state.sourceMode === 'balance') {
        return {
            mode: 'balance',
            periodMode: BALANCE_SOURCE_PERIOD_MODE,
            balanceTreeSlug: state.selectedTreeSlug,
            observationDate: state.balanceDateScenario.observationDate,
            valuationType: state.balanceDateScenario.valuationType,
            scenario: state.balanceDateScenario.scenario,
            filterRules: state.filterRules?.length ? state.filterRules as unknown as Record<string, unknown>[] : undefined,
        };
    }

    return {
        mode: 'filter',
        markets: state.scopeFilter.markets,
        products: state.scopeFilter.products,
        supplyPaths: state.scopeFilter.supplyPaths,
        glAccounts: state.scopeFilter.glAccounts,
        periodMode: state.periodMode === 'prices' ? 'valuations' : state.periodMode,
        currency: currencyFromSimulationTarget(state.target),
        valuationType: state.dateScenario.valuationType,
        observationDate: state.dateScenario.observationDate,
        scenario: state.dateScenario.scenario,
        periodFrom: state.scopeFilter.periodFrom,
        periodTo: state.scopeFilter.periodTo,
        filterRules: state.filterRules?.length ? state.filterRules as unknown as Record<string, unknown>[] : undefined,
    };
};
