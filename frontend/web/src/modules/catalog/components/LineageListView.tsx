import type { LineageEdge, LineageNode } from '@shared/api/generated';
import { Empty, Space, Tag, Typography } from 'antd';
import { useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import LineageAssetChip from './LineageAssetChip';
import { STAGE_ORDER, TYPE_COLOR, buildFlowRows } from './lineageFlow';
import './lineageViews.css';

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
  const interactive = !node.unresolved;
  return (
    <LineageAssetChip
      assetType={node.asset_type}
      title={node.display_name}
      unresolved={node.unresolved}
      actor={actor}
      interactive={interactive}
      onClick={() => interactive && navigate(`/objects/${node.id}`)}
    />
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
