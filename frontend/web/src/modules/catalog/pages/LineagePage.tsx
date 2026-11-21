import { ArrowLeftOutlined, ExportOutlined } from '@ant-design/icons';
import { FreshnessBar } from '@shared/ui/portal';
import { Alert, Button, Select, Spin, Typography } from 'antd';
import { useMemo } from 'react';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { ASSET_TYPE_LABELS } from '../assetTypes';
import ExtractionLoadsPanel from '../components/ExtractionLoadsPanel';
import LineageGraph from '../components/LineageGraph';
import UnresolvedTargetsAlert from '../components/UnresolvedTargetsAlert';
import { LINEAGE_PICKER_TYPES, useCatalogAsset, useCatalogLineage, useCatalogLineagePicker } from '../queries';

const TYPE_ORDER = new Map(LINEAGE_PICKER_TYPES.map((type, index) => [type, index]));

const LineagePage = () => {
  const { assetId } = useParams<{ assetId: string }>();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const view = searchParams.get('view') === 'map' ? 'map' : 'list';
  const pickerQueries = useCatalogLineagePicker();
  const lineageQuery = useCatalogLineage(assetId);
  const selectedAssetQuery = useCatalogAsset(assetId);
  const lineage = lineageQuery.isError ? undefined : lineageQuery.data;
  const options = pickerQueries.flatMap((query) =>
    (query.data?.items ?? []).map((item) => ({
      value: item.id,
      type: item.asset_type,
      label: `${item.display_name || item.name || item.qualified_name} · ${ASSET_TYPE_LABELS[item.asset_type] ?? item.asset_type}`,
    }))
  ).sort((a, b) => {
        const typeDiff = (TYPE_ORDER.get(a.type as (typeof LINEAGE_PICKER_TYPES)[number]) ?? 99)
          - (TYPE_ORDER.get(b.type as (typeof LINEAGE_PICKER_TYPES)[number]) ?? 99);
        if (typeDiff !== 0) {
          return typeDiff;
        }
        return a.label.localeCompare(b.label);
  });

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
    <div className="lineage-page">
      <header className="lineage-page__header">
        <Typography.Title level={2} style={{ margin: 0 }}>
          Lineage
        </Typography.Title>
        <Typography.Text type="secondary">Откуда поступают данные и куда передаются</Typography.Text>
      </header>
      <div className="lineage-page__toolbar">
        <div className="lineage-page__picker">
          <label htmlFor="lineage-object-picker">Объект</label>
          <Select
            id="lineage-object-picker"
            showSearch
            allowClear
            optionFilterProp="label"
            placeholder="Найти объект или выбрать источник…"
            style={{ width: '100%', minWidth: 0 }}
            value={assetId}
            options={options}
            loading={pickerQueries.some((query) => query.isFetching)}
            notFoundContent={pickerQueries.some((query) => query.isPending) ? 'Загрузка…' : pickerQueries.some((query) => query.isError) ? 'Список недоступен' : 'Нет объектов'}
            onChange={(value) => navigate(`${value ? `/lineage/${value}` : '/lineage'}?view=${view}`)}
          />
        </div>
        {assetId ? (
          <Button type="text" icon={<ArrowLeftOutlined />} onClick={() => navigate(`/lineage?view=${view}`)}>
            Все источники
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
      {pickerQueries.some((query) => query.isError) ? <Alert type="error" showIcon message="Не удалось загрузить часть списка объектов" /> : null}
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

export default LineagePage;
