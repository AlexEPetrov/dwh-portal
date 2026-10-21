import { getAssetLineage, listAssets, listLineageRoots } from '@shared/api/generated';
import type { AssetListItem, LineageResponse, LineageRootsResponse } from '@shared/api/generated';
import { ExperimentOutlined } from '@ant-design/icons';
import { Alert, Button, Card, Empty, Select, Space, Typography } from 'antd';
import { useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import ExtractionLoadsPanel from '../components/ExtractionLoadsPanel';
import { FreshnessBar } from '@shared/ui/portal';
import LineageGraph from '../components/LineageGraph';

const LINEAGE_PICKER_TYPES = [
  'DATA_SOURCE',
  'EXTRACTION_SOURCE',
  'PROCESS',
  'TABLE',
  'VIEW',
  'STORAGE_LOCATION',
] as const;

const TYPE_ORDER = new Map(LINEAGE_PICKER_TYPES.map((type, index) => [type, index]));

const LineagePage = () => {
  const { assetId } = useParams<{ assetId: string }>();
  const navigate = useNavigate();
  const [options, setOptions] = useState<Array<{ value: string; label: string; type: string }>>([]);
  const [lineage, setLineage] = useState<LineageResponse | LineageRootsResponse | null>(null);

  useEffect(() => {
    Promise.all(
      LINEAGE_PICKER_TYPES.map((type) =>
        listAssets({ type, status: 'active', pageSize: 100 }).then((payload) =>
          payload.items.map((item: AssetListItem) => ({
            value: item.id,
            type: item.asset_type,
            label: `[${item.asset_type}] ${item.display_name || item.name || item.qualified_name}`,
          }))
        )
      )
    ).then((groups) => {
      const flat = groups.flat();
      flat.sort((a, b) => {
        const typeDiff = (TYPE_ORDER.get(a.type as (typeof LINEAGE_PICKER_TYPES)[number]) ?? 99)
          - (TYPE_ORDER.get(b.type as (typeof LINEAGE_PICKER_TYPES)[number]) ?? 99);
        if (typeDiff !== 0) {
          return typeDiff;
        }
        return a.label.localeCompare(b.label);
      });
      setOptions(flat);
    });
  }, []);

  useEffect(() => {
    let cancelled = false;
    const request = assetId ? getAssetLineage({ assetId }) : listLineageRoots();
    request.then((payload) => {
      if (!cancelled) {
        setLineage(payload);
      }
    });
    return () => {
      cancelled = true;
    };
  }, [assetId]);

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

  const selectedIsExtraction = options.some(
    (item) => item.value === assetId && item.type === 'EXTRACTION_SOURCE'
  );

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
      {assetId && lineage?.unresolved_targets.length ? (
        <Alert
          type="warning"
          showIcon
          message="Нерешённые цели loader metadata"
          description={lineage.unresolved_targets.map((item) => item.qualified_name).join(', ')}
        />
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
        {lineage ? (
          <LineageGraph
            nodes={lineage.nodes}
            edges={lineage.edges}
            selectedAssetId={assetId}
            fillHeight
            syncViewInUrl
            rootsOverview={!assetId}
          />
        ) : (
          <Empty description="Загрузка lineage…" />
        )}
      </div>
      {selectedIsExtraction && assetId ? (
        <ExtractionLoadsPanel key={assetId} assetId={assetId} hideWhenUnavailable compact />
      ) : null}
    </div>
  );
};

export default LineagePage;
