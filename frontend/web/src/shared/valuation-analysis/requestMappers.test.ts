import assert from 'node:assert/strict';
import test from 'node:test';
import { buildSimulationCombinedSourceParams } from './requestMappers';

const filterState = {
    sourceMode: 'filter' as const,
    periodMode: 'valuations' as const,
    target: 'value_rub' as const,
    dateScenario: { observationDate: '2026-07-31', scenario: null, valuationType: 'eod' },
    balanceDateScenario: { observationDate: '', scenario: null, valuationType: null },
    selectedTreeSlug: undefined,
    scopeFilter: {
        markets: [],
        products: [],
        supplyPaths: [],
        glAccounts: [],
        periodFrom: '2026-01-01',
        periodTo: '2026-12-01',
    },
};

test('changed filter period is mapped to changed simulation request parameters', () => {
    const initial = buildSimulationCombinedSourceParams(filterState);
    const changed = buildSimulationCombinedSourceParams({
        ...filterState,
        scopeFilter: { ...filterState.scopeFilter, periodFrom: '2026-04-01' },
    });

    assert.equal(initial.periodStart, '2026-01-01');
    assert.equal(changed.periodStart, '2026-04-01');
    assert.notDeepEqual(changed, initial);
});

test('liquidity analysis can reuse the selected valuation period and value target', () => {
    const params = buildSimulationCombinedSourceParams(filterState);

    assert.equal(params.periodMode, 'valuations');
    assert.equal(params.target, 'value_rub');
});
