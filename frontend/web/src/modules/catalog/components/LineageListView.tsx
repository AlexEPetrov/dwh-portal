import type { LineageEdge, LineageNode } from '@shared/api/generated';
import { Empty, Space, Tag, Typography } from 'antd';
import { useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import LineageAssetChip from './LineageAssetChip';
import { STAGE_ORDER, TYPE_COLOR, buildFlowRows, flowLabelFor } from './lineageFlow';
import './lineageViews.css';

type Props = {
  nodes: LineageNode[];
  edges: LineageEdge[];
  selectedAssetId?: string;
  onSelectInLineage?: (assetId: string) => void;
  rootsOverview?: boolean;
};

const NodeCard = ({
  node,
  actor = false,
  selected = false,
  onSelectInLineage,
}: {
  node: LineageNode;
  actor?: boolean;
  selected?: boolean;
  onSelectInLineage?: (assetId: string) => void;
}) => {
  const navigate = useNavigate();
  const interactive = !node.unresolved;
  return (
    <LineageAssetChip
      assetType={node.asset_type}
      title={node.display_name}
      unresolved={node.unresolved}
      actor={actor}
      selected={selected}
      interactive={interactive}
      onOpenObject={interactive ? () => navigate(`/objects/${node.id}`) : undefined}
      onSelectInLineage={
        interactive && onSelectInLineage ? () => onSelectInLineage(node.id) : undefined
      }
    />
  );
};

const Arrow = ({ label }: { label: string }) => (
  <Typography.Text type="secondary" style={{ whiteSpace: 'nowrap', flex: '0 0 auto' }}>
    — {label} →
  </Typography.Text>
);

const LineageListView = ({
  nodes,
  edges,
  selectedAssetId,
  onSelectInLineage,
  rootsOverview = false,
}: Props) => {
  const stages = useMemo(() => {
    const present = new Set(nodes.map((node) => node.asset_type));
    return STAGE_ORDER.filter((type) => present.has(type));
  }, [nodes]);

  const rows = useMemo(() => buildFlowRows(nodes, edges), [nodes, edges]);

  if (!nodes.length) {
    return (
      <Empty
        description={
          rootsOverview ? 'Нет корневых объектов lineage' : 'Нет lineage для выбранного объекта'
        }
      />
    );
  }
  if (rootsOverview) {
    return (
      <Space direction="vertical" size={16} style={{ width: '100%' }}>
        <Typography.Paragraph type="secondary" style={{ marginBottom: 0 }}>
          Корневые объекты: DATA_SOURCE и EXTRACTION_SOURCE без родительского источника. Нажмите
          прицел, чтобы открыть цепочку.
        </Typography.Paragraph>
        {stages.map((type) => (
          <Space key={type} direction="vertical" size={8} style={{ width: '100%' }}>
            <Tag color={TYPE_COLOR[type]}>{type}</Tag>
            <Space wrap size={8}>
              {nodes
                .filter((node) => node.asset_type === type)
                .map((node) => (
                  <NodeCard
                    key={node.id}
                    node={node}
                    selected={node.id === selectedAssetId}
                    onSelectInLineage={onSelectInLineage}
                  />
                ))}
            </Space>
          </Space>
        ))}
      </Space>
    );
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
        Иконка прицела на чипе — выбрать объект в Lineage (остаётесь здесь). Стрелка наружу — карточка
        объекта. VIEW может порождаться несколькими TABLE.
      </Typography.Paragraph>
      {rows.map((row) => (
        <div key={row.key} className="lineage-list-hop">
          <NodeCard
            node={row.left}
            selected={row.left.id === selectedAssetId}
            onSelectInLineage={onSelectInLineage}
          />
          {row.actor ? (
            <>
              <Arrow label={row.inLabel ?? flowLabelFor('READS_FROM')} />
              <NodeCard
                node={row.actor}
                actor
                selected={row.actor.id === selectedAssetId}
                onSelectInLineage={onSelectInLineage}
              />
              <Arrow label={row.flowLabel} />
            </>
          ) : (
            <Arrow label={row.flowLabel} />
          )}
          <NodeCard
            node={row.right}
            selected={row.right.id === selectedAssetId}
            onSelectInLineage={onSelectInLineage}
          />
        </div>
      ))}
    </Space>
  );
};

export default LineageListView;
