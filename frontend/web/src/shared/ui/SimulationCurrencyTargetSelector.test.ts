import assert from 'node:assert/strict';
import test from 'node:test';
import { buildSimulationPeriodModeUpdate } from './SimulationCurrencyTargetSelector';

test('updates period mode and its compatible target atomically', () => {
    assert.deepEqual(buildSimulationPeriodModeUpdate('value_rub', 'prices'), {
        periodMode: 'prices',
        target: 'price_rub',
    });
    assert.deepEqual(buildSimulationPeriodModeUpdate('price_usd', 'payments'), {
        periodMode: 'payments',
        target: 'value_usd',
    });
});
