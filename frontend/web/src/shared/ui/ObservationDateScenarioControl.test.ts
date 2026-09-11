import assert from 'node:assert/strict';
import test from 'node:test';

import {
    resolveAvailableValuationType,
    shouldLoadValuationTypes,
    type ValuationTypeOption,
} from '../valuationType';

const options: ValuationTypeOption[] = [
    { value: 'custom-a' },
    { value: 'custom-b' },
];

test('keeps the current valuation type after options refresh when it remains available', () => {
    assert.equal(resolveAvailableValuationType(options, 'custom-b'), 'custom-b');
});

test('selects the first valid valuation type after date or run-mode options refresh', () => {
    assert.equal(resolveAvailableValuationType(options, 'old-type'), 'custom-a');
});

test('clears the valuation type when refreshed options are empty', () => {
    assert.equal(resolveAvailableValuationType([], 'old-type'), null);
});

test('loads valuation types when the parent supplies an observation date before mount', () => {
    assert.equal(shouldLoadValuationTypes(true, '2026-07-31'), true);
    assert.equal(shouldLoadValuationTypes(true, ''), false);
    assert.equal(shouldLoadValuationTypes(false, '2026-07-31'), false);
});
