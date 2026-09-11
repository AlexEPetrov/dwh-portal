import type { LineageEdge, LineageNode } from '@shared/api/generated';
import { Card, Empty, Space, Tag, Typography } from 'antd';
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

type Props = {
  nodes: LineageNode[];
  edges: LineageEdge[];
};

const LineageGraph = ({ nodes, edges }: Props) => {
  const navigate = useNavigate();
  if (!nodes.length) {
    return <Empty description="Нет lineage для выбранного объекта" />;
  }
  const byId = new Map(nodes.map((node) => [node.id, node]));
  return (
    <Space direction="vertical" size={12} style={{ width: '100%' }}>
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
