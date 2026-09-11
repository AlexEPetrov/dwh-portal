import { getAssetLineage, listAssets } from '@shared/api/generated';
import type { AssetListItem, LineageResponse } from '@shared/api/generated';
import { Alert, Card, Empty, Select, Typography } from 'antd';
import { useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import FreshnessBar from '../components/FreshnessBar';
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
  const [lineage, setLineage] = useState<LineageResponse | null>(null);

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
    if (!assetId) {
      setLineage(null);
      return undefined;
    }
    let cancelled = false;
    getAssetLineage({ assetId }).then((payload) => {
      if (!cancelled) {
        setLineage(payload);
      }
    });
    return () => {
      cancelled = true;
    };
  }, [assetId]);

  const chainHint = useMemo(() => {
    if (!lineage) {
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
  }, [lineage]);

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
          DATA_SOURCE предоставляет EXTRACTION_SOURCE → STORAGE → PROCESS → TABLE/VIEW. Представления:
          список hops и граф зависимостей (React Flow).
        </Typography.Paragraph>
        <FreshnessBar items={lineage?.collector_freshness} />
      </div>
      <Card style={{ flex: '0 0 auto' }}>
        <Select
          showSearch
          optionFilterProp="label"
          placeholder="Выберите DATA_SOURCE / EXTRACTION / PROCESS / TABLE…"
          style={{ width: '100%', maxWidth: 640 }}
          value={assetId}
          options={options}
          onChange={(value) => navigate(`/lineage/${value}`)}
        />
      </Card>
      {lineage?.unresolved_targets.length ? (
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
          <LineageGraph nodes={lineage.nodes} edges={lineage.edges} fillHeight />
        ) : (
          <Empty description="Выберите объект — для демо удобнее DATA_SOURCE (ICE / CME Group)" />
        )}
      </div>
    </div>
  );
};

export default LineagePage;
