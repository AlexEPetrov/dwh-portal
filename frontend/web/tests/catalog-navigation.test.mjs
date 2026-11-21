import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';
import { CATALOG_ASSET_TYPES, OVERVIEW_ASSET_TYPES, catalogTypeUrl } from '../src/modules/catalog/assetTypes.ts';
import { readCatalogFilters, updateCatalogFilters } from '../src/modules/catalog/navigation.ts';
import { matchingResultsOption, overviewSearchParams, overviewSearchUrl } from '../src/modules/catalog/search.ts';

test('overview searches all databases and types with bounded server-side suggestions', () => {
    assert.deepEqual(overviewSearchParams('  Аргус & 東京  '), {
        q: 'Аргус & 東京', status: 'active', sort: 'qualified_name', page: 1, pageSize: 20,
    });
    assert.equal(overviewSearchParams('   ').q, undefined);
    for (const filter of ['database', 'schema', 'type', 'source']) {
        assert.equal(filter in overviewSearchParams('prices'), false);
    }
});

test('full results navigation preserves the same query without restricting a database', () => {
    const url = new URL(overviewSearchUrl(' Аргус & 東京 / 100% + '), 'https://portal.invalid');
    assert.equal(url.pathname, '/objects');
    assert.deepEqual(Object.fromEntries(url.searchParams), { q: 'Аргус & 東京 / 100% +', status: 'active' });
});

test('overview uses debounced server search without local filtering or type preloading', () => {
    const source = readFileSync(new URL('../src/modules/catalog/components/OverviewSearch.tsx', import.meta.url), 'utf8');
    assert.ok(source.includes('useCatalogAssets(overviewSearchParams(queryText), Boolean(currentText) && !isDebouncing)'));
    assert.ok(source.includes('filterOption={false}'));
    assert.ok(source.includes('searchValue={searchText}'));
    assert.ok(source.includes('!currentText || isDebouncing ? [] : assetsQuery.data?.items'));
    assert.ok(source.includes('clearTimeout(timer)'));
    assert.ok(!source.includes('useCatalogLineagePicker'));
    assert.ok(source.includes('overviewSearchUrl(queryText)'));
    assert.ok(source.includes("description: item.description ?? ''"));
    assert.ok(source.includes('option.data.qualifiedName'));
});

test('matching-results action is only selectable for confirmed nonempty matches', () => {
    for (const [query, total, ready] of [['', 864, true], ['   ', 864, true],
    ['prices', 0, true], ['prices', undefined, true], ['prices', 50, false]]) {
        assert.deepEqual(matchingResultsOption(query, total, ready), []);
    }
    const [action] = matchingResultsOption('Аргус', 43, true);
    assert.equal(action.kind, 'matches');
    assert.equal(action.label, 'Показать все подходящие (43)');
    assert.ok(!/^[0-9a-f-]{36}$/i.test(action.value));
    const source = readFileSync(new URL('../src/modules/catalog/components/OverviewSearch.tsx', import.meta.url), 'utf8');
    assert.ok(source.includes("option.kind === 'matches' ? overviewSearchUrl(queryText)"));
    assert.ok(source.includes('...matchingResultsOption(currentText, total, !isLoading && !hasError)'));
    assert.ok(!source.includes('Показано ${'));
    assert.ok(!source.includes('Все результаты'));
});

test('every type tile links to active objects with the same exact type and no database assumption', () => {
    assert.equal(CATALOG_ASSET_TYPES.length, 9);
    for (const { key } of CATALOG_ASSET_TYPES) {
        const params = new URL(catalogTypeUrl(key), 'https://portal.invalid').searchParams;
        assert.deepEqual(Object.fromEntries(params), { type: key, status: 'active' });
        assert.equal(readCatalogFilters(params).type, key);
    }
    const menu = readFileSync(new URL('../src/modules/catalog/menu.tsx', import.meta.url), 'utf8');
    assert.ok(menu.includes("path: '/objects', label: 'Все объекты'"));
});

test('overview replaces storage cards with type links and an independent live-files panel', () => {
    const source = readFileSync(new URL('../src/modules/catalog/pages/OverviewPage.tsx', import.meta.url), 'utf8');
    assert.ok(source.includes('catalogTypeUrl(key)'));
    assert.ok(source.includes('asset_counts.by_type'));
    assert.ok(source.includes('<RecentLoadsPanel />'));
    assert.ok(!source.includes('Общий объём'));
    assert.ok(!source.includes('Объём по схемам'));
    const panel = readFileSync(new URL('../src/modules/catalog/components/RecentLoadsPanel.tsx', import.meta.url), 'utf8');
    assert.ok(panel.includes('useCatalogRecentLoads()'));
    assert.ok(panel.includes('query.isError'));
    assert.ok(panel.includes('!data.available'));
    assert.ok(panel.includes('row.database'));
});

test('overview shows eight non-database tiles in four columns with changes in the header', () => {
    assert.equal(OVERVIEW_ASSET_TYPES.length, 8);
    assert.ok(OVERVIEW_ASSET_TYPES.every(({ key }) => key !== 'DATABASE'));
    assert.ok(CATALOG_ASSET_TYPES.some(({ key }) => key === 'DATABASE'));
    const source = readFileSync(new URL('../src/modules/catalog/pages/OverviewPage.tsx', import.meta.url), 'utf8');
    assert.ok(source.includes('OVERVIEW_ASSET_TYPES.map'));
    assert.ok(source.includes('xs={24} sm={12} lg={6}'));
    assert.ok(source.includes("marginLeft: 'auto'"));
    assert.ok(source.includes('Изменения за 24 часа: {data.recent_changes.total}'));
    assert.ok(!source.includes('<Statistic title="Изменения за 24 часа"'));
});

test('query-only navigation preserves the mounted page and input focus', () => {
    const source = readFileSync(new URL('../../app-shell/src/routing/RouteSuspense.tsx', import.meta.url), 'utf8');
    assert.ok(source.includes('key={location.pathname}'));
    assert.ok(!source.includes('key={location.key}'));
});

test('object search isolates query notifications and loading in the grid subtree', () => {
    const source = readFileSync(new URL('../src/modules/catalog/pages/ObjectsPage.tsx', import.meta.url), 'utf8');
    const grid = source.slice(source.indexOf('const ObjectsGrid ='), source.indexOf('const ObjectsHeader ='));
    const page = source.slice(source.indexOf('const ObjectsPage ='));
    assert.ok(grid.includes('useCatalogAssets('));
    assert.ok(grid.includes('loading={assetsQuery.isPending || assetsQuery.isFetching}'));
    assert.ok(grid.includes('if (freshness) onFreshness(freshness)'));
    assert.ok(!page.includes('useCatalogAssets('));
    assert.ok(!page.includes('assetsQuery'));
    assert.ok(page.includes('<ObjectsGrid filters={filters} onFreshness={onFreshness} />'));
    assert.ok(page.includes('<ObjectsHeader freshness={freshness} />'));
});

test('restores every server-authored search filter without changing identifiers', () => {
    const values = {
        q: 'Цена & 東京 | 100%', database: 'dwh/one', schema: 'raw+market',
        type: 'TABLE,MATERIALIZED_VIEW', source: 'postgres_sql', status: 'deleted',
        changed_since: '2026-11-21T10:00:00+03:00', sort: 'qualified_name',
    };
    const restored = readCatalogFilters(new URLSearchParams(values));
    assert.deepEqual(restored, {
        q: values.q, database: values.database, schema: values.schema, type: values.type,
        source: values.source, status: 'deleted', changedSince: values.changed_since,
        sort: 'qualified_name',
    });
});

test('plain objects route retains active browsing defaults and no extra filters', () => {
    const filters = readCatalogFilters(new URLSearchParams());
    assert.equal(filters.status, 'active');
    assert.equal(filters.sort, 'qualified_name');
    for (const key of ['q', 'database', 'schema', 'type', 'source', 'changedSince']) {
        assert.equal(filters[key], undefined);
    }
});

test('updates preserve other filters and clear resets the first page without mutating input', () => {
    const original = new URLSearchParams('type=VIEW&database=dwh&page=4&other=keep');
    const updated = updateCatalogFilters(original, { q: 'ice_brent', changedSince: '2026-11-21T00:00:00Z' });
    assert.equal(updated.get('type'), 'VIEW');
    assert.equal(updated.get('database'), 'dwh');
    assert.equal(updated.get('changed_since'), '2026-11-21T00:00:00Z');
    assert.equal(updated.get('other'), 'keep');
    assert.equal(updated.has('page'), false);
    assert.equal(original.get('page'), '4');
    const cleared = updateCatalogFilters(updated, { type: '', q: undefined, database: null, changedSince: '' });
    assert.equal(cleared.toString(), 'other=keep');
});

test('status cannot inject unrelated request options or claim a model-defined endpoint', () => {
    const result = readCatalogFilters(new URLSearchParams('status=invalid&url=https://evil.invalid&sort=arbitrary'));
    assert.equal(result.status, 'active');
    assert.equal(result.sort, 'qualified_name');
    assert.equal('url' in result, false);
});

test('server navigation destinations correspond to registered Portal/Universe routes', () => {
    const routes = readFileSync(new URL('../src/modules/catalog/index.tsx', import.meta.url), 'utf8');
    for (const path of ['/objects', '/objects/:assetId', '/lineage/:assetId',
        '/lineage/universe', '/lineage/universe/:assetId']) {
        assert.ok(routes.includes(`path: '${path}'`), `Missing verified route: ${path}`);
    }
});
