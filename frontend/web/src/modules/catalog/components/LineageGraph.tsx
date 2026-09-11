import type { LineageEdge, LineageNode } from '@shared/api/generated';
import { Card, Empty, Space, Tag, Typography } from 'antd';
import { useMemo } from 'react';
import { useNavigate } from 'react-router-dom';

const TYPE_COLOR: Record<string, string> = {
  DATA_SOURCE: 'purple',
  EXTRACTION_SOURCE: 'blue',
  STORAGE_LOCATION: 'gold',
  PROCESS: 'cyan',
  TABLE: 'green',
  VIEW: 'green',
  MATERIALIZED_VIEW: 'green',
};

const STAGE_ORDER = [
  'DATA_SOURCE',
  'EXTRACTION_SOURCE',
  'STORAGE_LOCATION',
  'PROCESS',
  'TABLE',
  'VIEW',
  'MATERIALIZED_VIEW',
];

type Props = {
  nodes: LineageNode[];
  edges: LineageEdge[];
};

const LineageGraph = ({ nodes, edges }: Props) => {
  const navigate = useNavigate();
  const stages = useMemo(() => {
    const present = new Set(nodes.map((node) => node.asset_type));
    return STAGE_ORDER.filter((type) => present.has(type));
  }, [nodes]);

  if (!nodes.length) {
    return <Empty description="Нет lineage для выбранного объекта" />;
  }
  if (!edges.length) {
    return (
      <Empty description="У объекта нет data-flow рёбер (EXTRACTS_TO / READS_FROM / WRITES_TO). Выберите DATA_SOURCE или EXTRACTION_SOURCE." />
    );
  }

  const byId = new Map(nodes.map((node) => [node.id, node]));
  return (
    <Space direction="vertical" size={16} style={{ width: '100%' }}>
      <Space wrap size={4}>
        <Typography.Text type="secondary">Стадии в графе:</Typography.Text>
        {stages.map((type, index) => (
          <span key={type}>
            <Tag color={TYPE_COLOR[type]}>{type}</Tag>
            {index < stages.length - 1 ? <Typography.Text type="secondary"> → </Typography.Text> : null}
          </span>
        ))}
      </Space>
      {edges.map((edge) => {
        const from = byId.get(edge.from_asset_id);
        const to = byId.get(edge.to_asset_id);
        if (!from || !to) {
          return null;
        }
        return (
          <Space key={edge.id} align="center" wrap>
            <Card
              size="small"
              hoverable={!from.unresolved}
              onClick={() => !from.unresolved && navigate(`/objects/${from.id}`)}
            >
              <Space direction="vertical" size={2}>
                <Tag color={from.unresolved ? 'red' : TYPE_COLOR[from.asset_type]}>{from.asset_type}</Tag>
                <Typography.Text strong>{from.display_name}</Typography.Text>
              </Space>
            </Card>
            <Typography.Text type="secondary">{edge.relationship_type} →</Typography.Text>
            <Card
              size="small"
              hoverable={!to.unresolved}
              onClick={() => !to.unresolved && navigate(`/objects/${to.id}`)}
            >
              <Space direction="vertical" size={2}>
                <Tag color={to.unresolved ? 'red' : TYPE_COLOR[to.asset_type]}>{to.asset_type}</Tag>
                <Typography.Text strong>{to.display_name}</Typography.Text>
                {to.unresolved ? <Typography.Text type="danger">unresolved</Typography.Text> : null}
              </Space>
            </Card>
          </Space>
        );
      })}
    </Space>
  );
};

export default LineageGraph;
