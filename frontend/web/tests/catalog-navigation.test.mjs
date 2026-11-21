import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';
import { ASSET_TYPE_LABELS, CATALOG_ASSET_TYPES, OVERVIEW_ASSET_TYPES, catalogTypeUrl } from '../src/modules/catalog/assetTypes.ts';
import { inspectorConnections } from '../src/modules/catalog/components/lineageInspector.ts';
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

test('Universe chain nodes open Lineage while the roots overview stays inside Universe', () => {
    const page = readFileSync(new URL('../src/modules/catalog/pages/LineageUniversePage.tsx', import.meta.url), 'utf8');
    const select = page.slice(page.indexOf('const onSelect ='), page.indexOf('const openFocused ='));
    assert.ok(select.includes("mode === 'roots'"));
    assert.ok(select.includes('navigate(`/lineage/universe/${id}`, {'));
    assert.ok(select.includes('state: origin ? { fromRing: origin } : null'));
    assert.ok(select.includes('navigate(`/lineage/${id}`)'));
    assert.ok(!select.includes('/objects/'));
    const scene = readFileSync(new URL('../src/modules/catalog/components/LineageUniverseScene.tsx', import.meta.url), 'utf8');
    assert.ok(scene.includes('клик — Lineage · двойной — сюда'));
    assert.ok(scene.includes('Кликните, чтобы открыть Lineage объекта'));
    assert.ok(!scene.includes('Кликните, чтобы открыть карточку объекта'));
});

test('Universe freshness is disclosed from the header rather than obscured underneath it', () => {
    const page = readFileSync(new URL('../src/modules/catalog/pages/LineageUniversePage.tsx', import.meta.url), 'utf8');
    const header = page.slice(page.indexOf('<header'), page.indexOf('</header>'));
    const belowHeader = page.slice(page.indexOf('</header>'));
    assert.ok(header.includes('<Popover'));
    assert.ok(header.includes('trigger="click"'));
    assert.ok(header.includes('Актуальность метаданных'));
    assert.ok(header.includes('<FreshnessBar items={freshness} />'));
    assert.ok(header.includes('freshnessNotices'));
    assert.ok(!belowHeader.includes('<FreshnessBar'));
    const css = readFileSync(new URL('../src/modules/catalog/components/lineageUniverse.css', import.meta.url), 'utf8');
    assert.ok(css.includes('.lineage-universe-freshness.ant-btn'));
    assert.ok(css.includes('.lineage-universe-freshness-details .ant-tag'));
});

test('lineage display labels cover canonical types without changing their identifiers', () => {
    for (const { key } of CATALOG_ASSET_TYPES) {
        assert.equal(typeof ASSET_TYPE_LABELS[key], 'string');
        assert.ok(ASSET_TYPE_LABELS[key].length > 0);
    }
    assert.equal(ASSET_TYPE_LABELS.TABLE, 'Таблица');
    assert.equal(ASSET_TYPE_LABELS.PROCESS, 'Процесс');
});

test('compact lineage retains metadata details, explicit unresolved targets and extraction loads', () => {
    const page = readFileSync(new URL('../src/modules/catalog/pages/LineagePage.tsx', import.meta.url), 'utf8');
    assert.ok(page.includes('<FreshnessBar items={freshness} />'));
    assert.ok(page.includes('<details className="lineage-page__details">'));
    assert.ok(page.includes('<UnresolvedTargetsAlert key={assetId} targets={lineage.unresolved_targets} />'));
    assert.ok(page.includes('<ExtractionLoadsPanel key={assetId} assetId={assetId} hideWhenUnavailable compact />'));
    assert.ok(page.includes('lineageQuery.isError'));
    assert.ok(page.includes('в пределах глубины обхода'));
    assert.ok(!page.includes('Цепочка пока неполная'));
    assert.ok(!page.includes('Выберите DATA_SOURCE «ICE»'));
});

test('lineage object changes and source overview preserve the active view and Universe context', () => {
    const page = readFileSync(new URL('../src/modules/catalog/pages/LineagePage.tsx', import.meta.url), 'utf8');
    assert.ok(page.includes("searchParams.get('view') === 'map' ? 'map' : 'list'"));
    assert.ok(page.includes("`${value ? `/lineage/${value}` : '/lineage'}?view=${view}`"));
    assert.ok(page.includes('navigate(`/lineage?view=${view}`)'));
    assert.ok(page.includes("assetId ? `/lineage/universe/${assetId}` : '/lineage/universe'"));
});

test('lineage exposes focus reset and direct keyboard-accessible object actions', () => {
    const graph = readFileSync(new URL('../src/modules/catalog/components/LineageGraph.tsx', import.meta.url), 'utf8');
    assert.ok(graph.includes('onClick={onClearFocus}>Сбросить фокус'));
    assert.ok(graph.includes('Как пользоваться'));
    const chip = readFileSync(new URL('../src/modules/catalog/components/LineageAssetChip.tsx', import.meta.url), 'utf8');
    assert.ok(chip.includes('aria-label={`Открыть карточку: ${title}`}'));
    assert.ok(chip.includes('aria-label={`Открыть в Universe: ${title}`}'));
    assert.ok(!chip.includes('Dropdown'));
    assert.ok(chip.includes("event.key === 'Enter' || event.key === ' '"));
    assert.ok(chip.includes('Объект не найден в каталоге'));
});

test('inspector uses the existing flow direction for reads, writes and derived dependencies', () => {
    const nodes = ['table', 'process', 'target', 'view'].map((id) => ({
        id, asset_type: id === 'process' ? 'PROCESS' : id === 'view' ? 'VIEW' : 'TABLE',
        name: id, display_name: id, qualified_name: `dwh.raw.${id}`,
    }));
    const edges = [
        { id: 'read', from_asset_id: 'process', to_asset_id: 'table', relationship_type: 'READS_FROM' },
        { id: 'write', from_asset_id: 'process', to_asset_id: 'target', relationship_type: 'WRITES_TO' },
        { id: 'derived', from_asset_id: 'view', to_asset_id: 'target', relationship_type: 'DERIVED_FROM' },
    ];
    const original = structuredClone(edges);
    const process = inspectorConnections('process', nodes, edges);
    assert.deepEqual(process.incoming.map(({ node }) => node.id), ['table']);
    assert.deepEqual(process.outgoing.map(({ node }) => node.id), ['target']);
    const target = inspectorConnections('target', nodes, edges);
    assert.deepEqual(target.incoming.map(({ node }) => node.id), ['process']);
    assert.deepEqual(target.outgoing.map(({ node }) => node.id), ['view']);
    assert.deepEqual(edges, original, 'stored edge directions remain unchanged');
});

test('inspector preserves unresolved neighbours and does not infer links outside the payload', () => {
    const nodes = [
        { id: 'source', asset_type: 'DATA_SOURCE', name: 'source', display_name: 'source', qualified_name: 'source' },
        { id: 'missing', asset_type: 'TABLE', name: 'missing', display_name: 'missing', qualified_name: 'dwh.raw.missing', unresolved: true },
    ];
    const edges = [
        { id: 'known', from_asset_id: 'source', to_asset_id: 'missing', relationship_type: 'WRITES_TO' },
        { id: 'outside', from_asset_id: 'source', to_asset_id: 'outside', relationship_type: 'WRITES_TO' },
    ];
    const result = inspectorConnections('source', nodes, edges);
    assert.equal(result.outgoing.length, 1);
    assert.equal(result.outgoing[0].node.unresolved, true);
    assert.deepEqual(inspectorConnections('absent', nodes, edges), { incoming: [], outgoing: [] });
});

test('inspector persists across views and focus reset falls back to the route object', () => {
    const graph = readFileSync(new URL('../src/modules/catalog/components/LineageGraph.tsx', import.meta.url), 'utf8');
    assert.ok(graph.includes('assetId={focus?.id ?? selectedAssetId}'));
    assert.ok(graph.indexOf('<LineageInspector') > graph.indexOf('items={['));
    const inspector = readFileSync(new URL('../src/modules/catalog/components/LineageInspector.tsx', import.meta.url), 'utf8');
    assert.ok(inspector.includes('node.qualified_name'));
    assert.ok(inspector.includes('neighbour.unresolved'));
    assert.ok(inspector.includes('Нет связей в текущем графе'));
    assert.ok(!inspector.includes('useCatalogAsset'));
});

test('both lineage views mark exactly the inspector asset separately from the route object', () => {
    const graph = readFileSync(new URL('../src/modules/catalog/components/LineageGraph.tsx', import.meta.url), 'utf8');
    assert.equal(graph.split('inspectorAssetId={fillHeight ? focus?.id ?? selectedAssetId : undefined}').length - 1, 2);
    const list = readFileSync(new URL('../src/modules/catalog/components/LineageListView.tsx', import.meta.url), 'utf8');
    assert.ok(list.includes('inspected={row.left.id === inspectorAssetId}'));
    assert.ok(list.includes('inspected={row.right.id === inspectorAssetId}'));
    assert.ok(list.includes('inspected={row.actor.id === inspectorAssetId}'));
    const map = readFileSync(new URL('../src/modules/catalog/components/LineageMapView.tsx', import.meta.url), 'utf8');
    assert.ok(map.includes('inspected: node.id === inspectorAssetId'));
    const chip = readFileSync(new URL('../src/modules/catalog/components/LineageAssetChip.tsx', import.meta.url), 'utf8');
    assert.ok(chip.includes('В инспекторе'));
    assert.ok(chip.includes('Цепочка'));
    assert.ok(!chip.includes('>текущий<'));
    assert.ok(chip.indexOf('{title}') < chip.indexOf('В инспекторе'));
});

test('focus does not animate row transforms or change spacing inside the scroll region', () => {
    const list = readFileSync(new URL('../src/modules/catalog/components/LineageListView.tsx', import.meta.url), 'utf8');
    assert.ok(!list.includes('el.animate('));
    const css = readFileSync(new URL('../src/modules/catalog/components/lineageViews.css', import.meta.url), 'utf8');
    const focus = css.slice(css.indexOf('.lineage-list-focus {'), css.indexOf('@keyframes lineage-chip-enter'));
    assert.ok(focus.includes('gap: 16px'));
    assert.ok(focus.includes('padding: 0'));
    assert.ok(!focus.includes('animation:'));
    assert.ok(css.includes('scrollbar-gutter: stable'));
    assert.ok(css.includes('opacity: 0.12'));
    assert.ok(css.includes(':focus-within'));
    assert.ok(css.includes('@media (hover: none)'));
    const rows = css.slice(css.indexOf('.lineage-list-rows {'), css.indexOf('.lineage-list-hop {'));
    assert.ok(rows.includes('padding: 8px'), 'halo clearance is reserved even without focus');
    assert.ok(focus.includes('inset: -6px'), 'focus border sits outside cards without adding layout padding');
    assert.ok(css.includes('background: rgba(37, 99, 235, 0.07)'));
});
