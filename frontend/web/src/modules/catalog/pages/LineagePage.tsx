import { getAssetLineage, listAssets } from '@shared/api/generated';
import type { LineageResponse } from '@shared/api/generated';
import { Alert, Card, Empty, Select, Space, Typography } from 'antd';
import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import FreshnessBar from '../components/FreshnessBar';
import LineageGraph from '../components/LineageGraph';

const LineagePage = () => {
  const { assetId } = useParams<{ assetId: string }>();
  const navigate = useNavigate();
  const [options, setOptions] = useState<Array<{ value: string; label: string }>>([]);
  const [lineage, setLineage] = useState<LineageResponse | null>(null);

  useEffect(() => {
    listAssets({ type: 'TABLE', pageSize: 100 }).then((payload) => {
      setOptions(
        payload.items.map((item) => ({
          value: item.id,
          label: item.display_name || item.qualified_name,
        }))
      );
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

  return (
    <Space direction="vertical" size={16} style={{ width: '100%' }}>
      <div>
        <Typography.Title level={2} style={{ marginBottom: 4 }}>
          Lineage
        </Typography.Title>
        <FreshnessBar items={lineage?.collector_freshness} />
      </div>
      <Card>
        <Select
          showSearch
          optionFilterProp="label"
          placeholder="Выберите объект"
          style={{ width: 420 }}
          value={assetId}
          options={options}
          onChange={(value) => navigate(`/lineage/${value}`)}
        />
      </Card>
      {lineage?.unresolved_targets.length ? (
        <Alert
          type="warning"
          showIcon
          message="Есть нерешённые цели lineage"
          description={lineage.unresolved_targets.map((item) => item.qualified_name).join(', ')}
        />
      ) : null}
      {lineage ? <LineageGraph nodes={lineage.nodes} edges={lineage.edges} /> : <Empty description="Выберите объект" />}
    </Space>
  );
};

export default LineagePage;
