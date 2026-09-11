import type { LineageEdge, LineageNode } from '@shared/api/generated';
import { Card, Empty, Space, Tag, Typography } from 'antd';
import { useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  STAGE_ORDER,
  TYPE_COLOR,
  buildFlowRows,
} from './lineageFlow';

type Props = {
  nodes: LineageNode[];
  edges: LineageEdge[];
};

const NodeCard = ({
  node,
  actor = false,
}: {
  node: LineageNode;
  actor?: boolean;
}) => {
  const navigate = useNavigate();
  return (
    <Card
      size="small"
      hoverable={!node.unresolved}
      onClick={() => !node.unresolved && navigate(`/objects/${node.id}`)}
      style={
        actor
          ? {
              borderStyle: 'dashed',
              borderColor: '#13c2c2',
              background: 'rgba(19, 194, 194, 0.06)',
              minWidth: 140,
              maxWidth: 220,
            }
          : { minWidth: 160, maxWidth: 280 }
      }
    >
      <Space direction="vertical" size={2}>
        <Tag color={node.unresolved ? 'red' : TYPE_COLOR[node.asset_type]}>
          {actor ? 'PROCESS · actor' : node.asset_type}
        </Tag>
        <Typography.Text strong ellipsis style={{ maxWidth: actor ? 200 : 260 }}>
          {node.display_name}
        </Typography.Text>
        {node.unresolved ? <Typography.Text type="danger">unresolved</Typography.Text> : null}
      </Space>
    </Card>
  );
};

const Arrow = ({ label }: { label: string }) => (
  <Typography.Text type="secondary" style={{ whiteSpace: 'nowrap' }}>
    — {label} →
  </Typography.Text>
);

const LineageListView = ({ nodes, edges }: Props) => {
  const stages = useMemo(() => {
    const present = new Set(nodes.map((node) => node.asset_type));
    return STAGE_ORDER.filter((type) => present.has(type));
  }, [nodes]);

  const rows = useMemo(() => buildFlowRows(nodes, edges), [nodes, edges]);

  if (!nodes.length) {
    return <Empty description="Нет lineage для выбранного объекта" />;
  }
  if (!edges.length || !rows.length) {
    return (
      <Empty description="У объекта нет data-flow рёбер. Выберите DATA_SOURCE, EXTRACTION_SOURCE или PROCESS." />
    );
  }

  return (
    <Space direction="vertical" size={16} style={{ width: '100%' }}>
      <Space wrap size={4}>
        <Typography.Text type="secondary">Поток слева направо:</Typography.Text>
        {stages.map((type, index) => (
          <span key={type}>
            <Tag color={TYPE_COLOR[type]}>{type}</Tag>
            {index < stages.length - 1 ? <Typography.Text type="secondary"> → </Typography.Text> : null}
          </span>
        ))}
      </Space>
      <Typography.Paragraph type="secondary" style={{ marginBottom: 0 }}>
        DATA_SOURCE предоставляет EXTRACTION_SOURCE. PROCESS — актор посередине (source → process →
        target). View: table → view.
      </Typography.Paragraph>
      {rows.map((row) => (
        <Space key={row.key} align="center" wrap size="middle">
          <NodeCard node={row.left} />
          {row.actor ? (
            <>
              <Arrow label="из" />
              <NodeCard node={row.actor} actor />
              <Arrow label={row.flowLabel} />
            </>
          ) : (
            <Arrow label={row.flowLabel} />
          )}
          <NodeCard node={row.right} />
        </Space>
      ))}
    </Space>
  );
};

export default LineageListView;
