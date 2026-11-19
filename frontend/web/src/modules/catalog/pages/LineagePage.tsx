import { ExperimentOutlined } from '@ant-design/icons';
import { FreshnessBar } from '@shared/ui/portal';
import { Alert, Button, Card, Select, Space, Spin, Typography } from 'antd';
import { useMemo } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import ExtractionLoadsPanel from '../components/ExtractionLoadsPanel';
import LineageGraph from '../components/LineageGraph';
import UnresolvedTargetsAlert from '../components/UnresolvedTargetsAlert';
import { LINEAGE_PICKER_TYPES, useCatalogAsset, useCatalogLineage, useCatalogLineagePicker } from '../queries';

const TYPE_ORDER = new Map(LINEAGE_PICKER_TYPES.map((type, index) => [type, index]));

const LineagePage = () => {
  const { assetId } = useParams<{ assetId: string }>();
  const navigate = useNavigate();
  const pickerQueries = useCatalogLineagePicker();
  const lineageQuery = useCatalogLineage(assetId);
  const selectedAssetQuery = useCatalogAsset(assetId);
  const lineage = lineageQuery.isError ? undefined : lineageQuery.data;
  const options = pickerQueries.flatMap((query) =>
    (query.data?.items ?? []).map((item) => ({
      value: item.id,
      type: item.asset_type,
      label: `[${item.asset_type}] ${item.display_name || item.name || item.qualified_name}`,
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
    if (!hasSource) missing.push('DATA_SOURCE');
    if (!hasExtraction) missing.push('EXTRACTION_SOURCE');
    if (!hasProcess) missing.push('PROCESS');
    if (!hasTable) missing.push('TABLE/VIEW (нужен WRITES_TO из get_metadata())');
    return missing;
  }, [assetId, lineage]);

  const selectedIsExtraction = selectedAssetQuery.data?.asset_type === 'EXTRACTION_SOURCE'
    && selectedAssetQuery.data.source_provider === 'extraction_registry';

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
        minHeight: 0,
        gap: 16,
        width: '100%',
      }}
    >
      <div style={{ flex: '0 0 auto' }}>
        <Typography.Title level={2} style={{ marginBottom: 4 }}>
          Lineage
        </Typography.Title>
        <Typography.Paragraph type="secondary" style={{ marginBottom: 8 }}>
          По умолчанию — корневые объекты: все DATA_SOURCE и EXTRACTION_SOURCE без родительского
          источника. Выбор объекта открывает его цепочку (список hops и граф).
        </Typography.Paragraph>
        <FreshnessBar items={lineage?.collector_freshness} />
      </div>
      <Card style={{ flex: '0 0 auto' }}>
        <Space wrap style={{ width: '100%' }} size={12}>
          <Select
            showSearch
            allowClear
            optionFilterProp="label"
            placeholder="Все корни, или выберите объект…"
            style={{ width: 'min(100%, 640px)', minWidth: 280 }}
            value={assetId}
            options={options}
            loading={pickerQueries.some((query) => query.isFetching)}
            notFoundContent={pickerQueries.some((query) => query.isPending) ? 'Загрузка…' : pickerQueries.some((query) => query.isError) ? 'Список недоступен' : 'Нет объектов'}
            onChange={(value) => navigate(value ? `/lineage/${value}` : '/lineage')}
          />
          <Button
            type="primary"
            ghost
            icon={<ExperimentOutlined />}
            className="lineage-universe-entry"
            onClick={() =>
              navigate(assetId ? `/lineage/universe/${assetId}` : '/lineage/universe')
            }
          >
            Universe
          </Button>
        </Space>
      </Card>
      {pickerQueries.some((query) => query.isError) ? <Alert type="error" showIcon message="Не удалось загрузить часть списка объектов" /> : null}
      {selectedAssetQuery.isError ? <Alert type="error" showIcon message="Не удалось загрузить сведения выбранного объекта и доступность загрузок" description={selectedAssetQuery.error.message} /> : null}
      {assetId && selectedAssetQuery.isPending ? <Typography.Text type="secondary">Загрузка сведений выбранного объекта…</Typography.Text> : null}
      {lineageQuery.isFetching ? <Spin size="small" /> : null}
      {assetId && lineage?.unresolved_targets.length ? (
        <UnresolvedTargetsAlert key={assetId} targets={lineage.unresolved_targets} />
      ) : null}
      {chainHint ? (
        <Alert
          type="info"
          showIcon
          message="Цепочка пока неполная"
          description={`В графе нет: ${chainHint.join(', ')}. Выберите DATA_SOURCE «ICE» или пересоберите коллектор после появления get_metadata().`}
        />
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
      {selectedIsExtraction && assetId ? (
        <ExtractionLoadsPanel key={assetId} assetId={assetId} hideWhenUnavailable compact />
      ) : null}
    </div>
  );
};

export default LineagePage;
