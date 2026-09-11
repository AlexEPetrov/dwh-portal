import type { ValuationFilterPresetModel } from '@shared/api/generated/types.gen';
import dayjs from 'dayjs';
import assert from 'node:assert/strict';
import test from 'node:test';
import { formatPeriodBoundary, valuationScopeFromPreset } from './ValuationScopeFilter';

test('normalizes month selections to inclusive period boundaries', () => {
    const december = dayjs('2026-12-01');

    assert.equal(formatPeriodBoundary(december, 'monthly', 'from'), '2026-12-01');
    assert.equal(formatPeriodBoundary(december, 'monthly', 'to'), '2026-12-31');
});

test('normalizes year selections to inclusive period boundaries', () => {
    const year = dayjs('2026-01-01');

    assert.equal(formatPeriodBoundary(year, 'yearly', 'from'), '2026-01-01');
    assert.equal(formatPeriodBoundary(year, 'yearly', 'to'), '2026-12-31');
});

test('normalizes week selections to inclusive period boundaries', () => {
    const week = dayjs('2026-12-02');

    assert.equal(formatPeriodBoundary(week, 'weekly', 'from'), '2026-11-29');
    assert.equal(formatPeriodBoundary(week, 'weekly', 'to'), '2026-12-05');
});

test('keeps exact daily boundaries', () => {
    const day = dayjs('2026-12-02');

    assert.equal(formatPeriodBoundary(day, 'daily', 'from'), '2026-12-02');
    assert.equal(formatPeriodBoundary(day, 'daily', 'to'), '2026-12-02');
});

test('maps every supported JSON preset scope field', () => {
    const preset: ValuationFilterPresetModel = {
        id: 'mounted',
        name: 'Mounted preset',
        filters: {
            markets: ['industrial'],
            products: ['lng'],
            supply_paths: ['north'],
            gl_accounts: ['OP_TAX_DUTY'],
            period_mode: 'payments',
            period_from: '2026-01-01',
            period_to: '2026-03-31',
            observation_date: '2026-04-28',
        },
    };

    assert.deepEqual(valuationScopeFromPreset(preset, {
        markets: [], products: [], supplyPaths: [], glAccounts: [],
        periodFrom: '2025-01-01', periodTo: '2025-12-31', interval: 'weekly',
    }), {
        markets: ['industrial'],
        products: ['lng'],
        supplyPaths: ['north'],
        glAccounts: ['OP_TAX_DUTY'],
        periodFrom: '2026-01-01',
        periodTo: '2026-03-31',
        interval: 'weekly',
    });
});

test('materializes omitted optional preset lists as empty', () => {
    const preset: ValuationFilterPresetModel = {
        id: 'minimal',
        name: 'Minimal preset',
        filters: {
            period_from: '2026-01-01',
            period_to: '2026-12-31',
            observation_date: '2026-04-28',
        },
    };

    const scope = valuationScopeFromPreset(preset, {
        markets: ['old-market'], products: [], supplyPaths: [], glAccounts: [],
        periodFrom: '2025-01-01', periodTo: '2025-12-31',
    });

    assert.deepEqual(scope.markets, []);
    assert.deepEqual(scope.products, []);
    assert.deepEqual(scope.supplyPaths, []);
    assert.deepEqual(scope.glAccounts, []);
});

test('preserves current period when preset boundaries are omitted', () => {
    const preset: ValuationFilterPresetModel = {
        id: 'without-dates',
        name: 'Without dates',
        filters: {},
    };

    const scope = valuationScopeFromPreset(preset, {
        markets: [], products: [], supplyPaths: [], glAccounts: [],
        periodFrom: '2025-02-01', periodTo: '2025-11-30', interval: 'monthly',
    });

    assert.equal(scope.periodFrom, '2025-02-01');
    assert.equal(scope.periodTo, '2025-11-30');
});
