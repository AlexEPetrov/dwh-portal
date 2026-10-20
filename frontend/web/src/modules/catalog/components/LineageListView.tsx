import type { LineageEdge, LineageNode } from '@shared/api/generated';
import { Empty, Space, Tag, Tooltip, Typography } from 'antd';
import { useEffect, useMemo, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import LineageAssetChip from './LineageAssetChip';
import {
  STAGE_ORDER,
  TYPE_COLOR,
  buildFlowRows,
  flowLabelFor,
  focusFlowRows,
  originCaption,
  type FlowRow,
} from './lineageFlow';
import './lineageViews.css';

type Props = {
  nodes: LineageNode[];
  edges: LineageEdge[];
  selectedAssetId?: string;
  focusId?: string | null;
  focusAnchorKey?: string | null;
  onFocusNode?: (assetId: string, anchorKey?: string) => void;
  rootsOverview?: boolean;
};

const NodeCard = ({
  node,
  actor = false,
  selected = false,
  focused = false,
  onFocusNode,
}: {
  node: LineageNode;
  actor?: boolean;
  selected?: boolean;
  focused?: boolean;
  onFocusNode?: (assetId: string) => void;
}) => {
  const navigate = useNavigate();
  const interactive = !node.unresolved;
  const activate = interactive && onFocusNode ? () => onFocusNode(node.id) : undefined;
  return (
    <LineageAssetChip
      assetType={node.asset_type}
      title={node.display_name}
      hint={originCaption(node.qualified_name)}
      unresolved={node.unresolved}
      actor={actor}
      selected={selected}
      focused={focused}
      interactive={interactive}
      onOpenObject={interactive ? () => navigate(`/objects/${node.id}`) : undefined}
      onActivate={activate}
      onSelectInLineage={activate}
    />
  );
};

const Hop = ({
  row,
  dimmed,
  anchor = false,
  selectedAssetId,
  focusId,
  onFocusNode,
}: {
  row: FlowRow;
  dimmed: boolean;
  anchor?: boolean;
  selectedAssetId?: string;
  focusId?: string | null;
  onFocusNode?: (assetId: string, anchorKey?: string) => void;
}) => (
  <div
    className={dimmed ? 'lineage-list-hop is-dimmed' : 'lineage-list-hop'}
    data-lineage-anchor={anchor ? 'true' : undefined}
  >
    <NodeCard
      node={row.left}
      selected={row.left.id === selectedAssetId}
      focused={row.left.id === focusId}
      onFocusNode={onFocusNode ? (assetId) => onFocusNode(assetId, row.key) : undefined}
    />
    {row.actor ? (
      <>
        <Arrow label={row.inLabel ?? flowLabelFor('READS_FROM')} />
        <NodeCard
          node={row.actor}
          actor
          selected={row.actor.id === selectedAssetId}
          focused={row.actor.id === focusId}
          onFocusNode={onFocusNode ? (assetId) => onFocusNode(assetId, row.key) : undefined}
        />
        <Arrow label={row.flowLabel} />
      </>
    ) : (
      <Arrow label={row.flowLabel} />
    )}
    <NodeCard
      node={row.right}
      selected={row.right.id === selectedAssetId}
      focused={row.right.id === focusId}
      onFocusNode={onFocusNode ? (assetId) => onFocusNode(assetId, row.key) : undefined}
    />
  </div>
);

const ListRows = ({
  rows,
  clusterRef,
  anchorKey,
  dependencyKeys,
  selectedAssetId,
  focusId,
  onFocusNode,
}: {
  rows: FlowRow[];
  clusterRef: { current: HTMLDivElement | null };
  anchorKey: string | null;
  dependencyKeys: Set<string>;
  selectedAssetId?: string;
  focusId?: string | null;
  onFocusNode?: (assetId: string, anchorKey?: string) => void;
}) => {
  const anchorIndex = anchorKey ? rows.findIndex((row) => row.key === anchorKey) : -1;
  let clusterStart = anchorIndex;
  let clusterEnd = anchorIndex;
  if (anchorIndex >= 0) {
    while (clusterStart > 0 && dependencyKeys.has(rows[clusterStart - 1].key)) {
      clusterStart -= 1;
    }
    while (clusterEnd + 1 < rows.length && dependencyKeys.has(rows[clusterEnd + 1].key)) {
      clusterEnd += 1;
    }
  }
  const hopProps = { selectedAssetId, focusId, onFocusNode };
  const renderHop = (row: FlowRow, dimmed: boolean) => (
    <Hop
      key={row.key}
      row={row}
      dimmed={dimmed}
      anchor={row.key === anchorKey}
      {...hopProps}
    />
  );

  if (anchorIndex < 0) {
    return <div className="lineage-list-rows">{rows.map((row) => renderHop(row, false))}</div>;
  }

  const before = rows.slice(0, clusterStart);
  const cluster = rows.slice(clusterStart, clusterEnd + 1);
  const after = rows.slice(clusterEnd + 1);
  return (
    <div className="lineage-list-rows">
      {before.map((row) => renderHop(row, !dependencyKeys.has(row.key)))}
      <div className="lineage-list-focus" ref={clusterRef}>
        {cluster.map((row) => renderHop(row, false))}
      </div>
      {after.map((row) => renderHop(row, !dependencyKeys.has(row.key)))}
    </div>
  );
};

const Arrow = ({ label }: { label: string }) => (
  <Tooltip title={label}>
    <Typography.Text
      type="secondary"
      ellipsis
      style={{ maxWidth: 280, flex: '0 1 auto', whiteSpace: 'nowrap' }}
    >
      — {label} →
    </Typography.Text>
  </Tooltip>
);

const revealCluster = (cluster: HTMLElement) => {
  const anchor = cluster.querySelector<HTMLElement>('[data-lineage-anchor="true"]') ?? cluster;
  const scroller = cluster.closest('.lineage-list-scroll');
  if (!(scroller instanceof HTMLElement)) {
    anchor.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
    return;
  }
  const view = scroller.getBoundingClientRect();
  const box = cluster.getBoundingClientRect();
  const anchorBox = anchor.getBoundingClientRect();
  let delta = 0;
  const overflowTop = view.top + 8 - box.top;
  if (overflowTop > 1) {
    const roomBelowAnchor = anchorBox.bottom - (view.top + 32);
    delta -= Math.min(overflowTop, Math.max(0, roomBelowAnchor));
  }
  const overflowBottom = box.bottom - (view.bottom - 8);
  if (overflowBottom > 1) {
    const roomAboveAnchor = anchorBox.top - (view.top + 8) - delta;
    delta += Math.min(overflowBottom, Math.max(0, roomAboveAnchor));
  }
  if (Math.abs(delta) > 1) {
    scroller.scrollBy({ top: delta, behavior: 'smooth' });
  }
};

const LineageListView = ({
  nodes,
  edges,
  selectedAssetId,
  focusId = null,
  focusAnchorKey = null,
  onFocusNode,
  rootsOverview = false,
}: Props) => {
  const clusterRef = useRef<HTMLDivElement>(null);
  const stages = useMemo(() => {
    const present = new Set(nodes.map((node) => node.asset_type));
    return STAGE_ORDER.filter((type) => present.has(type));
  }, [nodes]);

  const baseRows = useMemo(() => buildFlowRows(nodes, edges), [nodes, edges]);
  const focused = useMemo(
    () => focusFlowRows(baseRows, focusId, focusAnchorKey),
    [baseRows, focusId, focusAnchorKey]
  );
  const rows = focused.rows;

  useEffect(() => {
    if (!focusId || !clusterRef.current) {
      return;
    }
    revealCluster(clusterRef.current);
  }, [focusId, focused.anchorKey, rows]);

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
          объект, чтобы открыть цепочку. Стрелка — карточка объекта.
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
                    focused={node.id === focusId}
                    onFocusNode={onFocusNode}
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
        Клик по объекту показывает его зависимости рядом и не сдвигает сам объект. Наведение
        показывает полное имя. Стрелка наружу — карточка объекта. Повторный клик возвращает общий
        список. VIEW может порождаться несколькими TABLE.
      </Typography.Paragraph>
      <ListRows
        rows={rows}
        clusterRef={clusterRef}
        anchorKey={focused.anchorKey}
        dependencyKeys={focused.dependencyKeys}
        selectedAssetId={selectedAssetId}
        focusId={focusId}
        onFocusNode={onFocusNode}
      />
    </Space>
  );
};

export default LineageListView;
