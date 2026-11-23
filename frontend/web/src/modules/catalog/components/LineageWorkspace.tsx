import { ArrowLeftOutlined, ExportOutlined } from '@ant-design/icons';
import { FreshnessBar } from '@shared/ui/portal';
import { Alert, Button, Select, Spin, Typography } from 'antd';
import { useEffect, useMemo, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { ASSET_TYPE_LABELS } from '../assetTypes';
import ExtractionLoadsPanel from './ExtractionLoadsPanel';
import LineageGraph from './LineageGraph';
import UnresolvedTargetsAlert from './UnresolvedTargetsAlert';
import { useCatalogAsset, useCatalogLineage, useCatalogLineagePicker } from '../queries';

const PICKER_DEBOUNCE_MS = 300;

const pickerLabel = (qualifiedName: string, type: string) =>
  `${qualifiedName} · ${ASSET_TYPE_LABELS[type] ?? type}`;

type Props = { assetId?: string } & (
  | { embedded?: false }
  | { embedded: true; assetId: string }
);

/** One lineage screen for the standalone route and the object card tab. */
const LineageWorkspace = ({ assetId, embedded = false }: Props) => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const view = searchParams.get('view') === 'map' ? 'map' : 'list';
  const [searchText, setSearchText] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const searchTerm = searchText.trim();
  const searchReady = Boolean(searchTerm) && searchTerm === debouncedSearch;
  useEffect(() => {
    const timeout = setTimeout(() => setDebouncedSearch(searchTerm), PICKER_DEBOUNCE_MS);
    return () => clearTimeout(timeout);
  }, [searchTerm]);

  const pickerQuery = useCatalogLineagePicker(debouncedSearch, !embedded && searchReady);
  const lineageQuery = useCatalogLineage(assetId);
  const selectedAssetQuery = useCatalogAsset(assetId);
  const lineage = lineageQuery.isError ? undefined : lineageQuery.data;
  const searchResult = searchReady ? pickerQuery.data : undefined;
  const pickerLoading = Boolean(searchTerm) && (!searchReady || pickerQuery.isFetching);
  const options = (searchResult?.items ?? []).map((item) => ({
    value: item.id,
    label: pickerLabel(item.qualified_name, item.asset_type),
  }));
  const selectedAsset = selectedAssetQuery.data;
  const pickerValue = assetId ? {
    value: assetId,
    label: selectedAsset ? pickerLabel(selectedAsset.qualified_name, selectedAsset.asset_type) : assetId,
  } : undefined;

  const chainHint = useMemo(() => {
    if (!assetId || !lineage) {
      return null;
    }
    const types = new Set(lineage.nodes.map((node) => node.asset_type));
    const hasSource = types.has('DATA_SOURCE');
    const hasExtraction = types.has('EXTRACTION_SOURCE');
    const hasTable = types.has('TABLE') || types.has('VIEW') || types.has('MATERIALIZED_VIEW');
    const hasProcess = types.has('PROCESS');
    if (hasSource && hasExtraction && hasProcess && hasTable) {
      return null;
    }
    const missing: string[] = [];
    if (!hasSource) missing.push('источники данных');
    if (!hasExtraction) missing.push('источники извлечения');
    if (!hasProcess) missing.push('процессы');
    if (!hasTable) missing.push('таблицы и представления');
    return missing;
  }, [assetId, lineage]);

  const freshness = lineage?.collector_freshness ?? [];
  const freshnessNotices = freshness.filter((item) => item.status !== 'SUCCESS').length;
  const selectedIsExtraction = selectedAssetQuery.data?.asset_type === 'EXTRACTION_SOURCE'
    && selectedAssetQuery.data.source_provider === 'extraction_registry';

  return (
    <div className={embedded ? 'lineage-page lineage-page--embedded' : 'lineage-page'}>
      {!embedded ? <header className="lineage-page__header">
        <Typography.Title level={2} style={{ margin: 0 }}>
          Lineage
        </Typography.Title>
        <Typography.Text type="secondary">Откуда поступают данные и куда передаются</Typography.Text>
      </header> : null}
      <div className="lineage-page__toolbar">
        {!embedded ? <div className="lineage-page__picker">
          <label htmlFor="lineage-object-picker">Объект</label>
          <Select
            id="lineage-object-picker"
            showSearch
            allowClear
            labelInValue
            filterOption={false}
            searchValue={searchText}
            onSearch={setSearchText}
            placeholder="Поиск по имени или описанию…"
            style={{ width: '100%', minWidth: 0 }}
            value={pickerValue}
            options={options}
            loading={pickerLoading}
            notFoundContent={
              !searchTerm ? 'Введите запрос для поиска'
                : pickerLoading ? 'Поиск…'
                : pickerQuery.isError ? 'Поиск недоступен' : 'Нет объектов'
            }
            onChange={(selection: typeof pickerValue) => {
              setSearchText('');
              navigate(`${selection ? `/lineage/${selection.value}` : '/lineage'}?view=${view}`);
            }}
          />
          {searchResult && searchResult.total > searchResult.items.length ? (
            <Typography.Text type="secondary">
              Показано {searchResult.items.length} из {searchResult.total}. Уточните запрос.
            </Typography.Text>
          ) : null}
        </div> : null}
        {!embedded && assetId ? (
          <Button type="text" icon={<ArrowLeftOutlined />} onClick={() => navigate(`/lineage?view=${view}`)}>
            Все источники
          </Button>
        ) : null}
        {embedded ? (
          <Button type="link" onClick={() => navigate(`/lineage/${assetId}?view=${view}`)}>
            Открыть на странице Lineage
          </Button>
        ) : null}
          <Button
            type="text"
            icon={<ExportOutlined />}
            className="lineage-universe-entry"
            onClick={() =>
              navigate(assetId ? `/lineage/universe/${assetId}` : '/lineage/universe')
            }
          >
            Открыть в Universe
          </Button>
      </div>
      {lineage ? (
        <details className="lineage-page__details">
          <summary>
            Актуальность метаданных · {freshness.length
              ? freshnessNotices
                ? `требуют внимания: ${freshnessNotices} из ${freshness.length} коллекторов`
                : 'все коллекторы обновлены'
              : 'снимки ещё не публиковались'}
          </summary>
          <Typography.Paragraph type="secondary">
            Статусы относятся к снимкам каталога, а не к свежести самих данных или успешности загрузок.
          </Typography.Paragraph>
          <FreshnessBar items={freshness} />
        </details>
      ) : null}
      {selectedAssetQuery.isError ? <Alert type="error" showIcon message="Не удалось загрузить сведения выбранного объекта и доступность загрузок" description={selectedAssetQuery.error.message} /> : null}
      {assetId && selectedAssetQuery.isPending ? <Typography.Text type="secondary">Загрузка сведений выбранного объекта…</Typography.Text> : null}
      {lineageQuery.isFetching ? <Spin size="small" /> : null}
      {assetId && lineage?.unresolved_targets.length ? (
        <UnresolvedTargetsAlert key={assetId} targets={lineage.unresolved_targets} />
      ) : null}
      <div style={{ flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column' }}>
        {lineageQuery.isError ? (
          <Alert type="error" showIcon message="Не удалось загрузить lineage" description={lineageQuery.error.message} />
        ) : lineage ? (
          <LineageGraph
            key={assetId ?? 'roots'}
            nodes={lineage.nodes}
            edges={lineage.edges}
            selectedAssetId={assetId}
            fillHeight
            syncViewInUrl
            rootsOverview={!assetId}
          />
        ) : (
          <Spin tip="Загрузка lineage…"><div style={{ minHeight: 160 }} /></Spin>
        )}
      </div>
      {chainHint ? (
        <details key={assetId} className="lineage-page__details">
          <summary>Некоторые этапы не представлены · Диагностика</summary>
          <Typography.Paragraph type="secondary">
            В доступном графе не найдены: {chainHint.join(', ')}. Показаны известные связи
            в пределах глубины обхода. Отсутствие этапа не означает ошибку: состав цепочки
            зависит от объекта и доступных метаданных.
          </Typography.Paragraph>
        </details>
      ) : null}
      {selectedIsExtraction && assetId ? (
        <ExtractionLoadsPanel key={assetId} assetId={assetId} hideWhenUnavailable compact />
      ) : null}
    </div>
  );
};

export default LineageWorkspace;
