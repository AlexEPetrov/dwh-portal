import type { LineageEdge, LineageNode } from '@shared/api/generated';
import { Empty, Space, Tag, Tooltip, Typography } from 'antd';
import { useLayoutEffect, useMemo, useRef, type CSSProperties } from 'react';
import { useNavigate } from 'react-router-dom';
import { ASSET_TYPE_LABELS } from '../assetTypes';
import LineageAssetChip from './LineageAssetChip';
import {
  STAGE_ORDER,
  TYPE_COLOR,
  buildFlowRows,
  flowLabelFor,
  focusFlowRows,
  originCaption,
  type FlowRow
} from './lineageFlow';
import './lineageViews.css';

type Props = {
  nodes: LineageNode[];
  edges: LineageEdge[];
  selectedAssetId?: string;
  inspectorAssetId?: string;
  focusId?: string | null;
  focusAnchorKey?: string | null;
  onFocusNode?: (assetId: string, anchorKey?: string) => void;
  rootsOverview?: boolean;
};

const extractionSourcesLabel = (count: number): string => {
  const mod10 = count % 10;
  const mod100 = count % 100;
  const word =
    mod10 === 1 && mod100 !== 11
      ? 'extraction source'
      : 'extraction sources';
  return `${count} ${word}`;
};

const NodeCard = ({
  node,
  actor = false,
  showType = true,
  selected = false,
  inspected = false,
  focused = false,
  detail = null,
  onFocusNode,
}: {
  node: LineageNode;
  actor?: boolean;
  /** False when the surrounding section already names the type (roots overview). */
  showType?: boolean;
  selected?: boolean;
  inspected?: boolean;
  focused?: boolean;
  /** Secondary line already loaded with the node. No extra request. */
  detail?: string | null;
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
      showType={showType}
      selected={selected}
      inspected={inspected}
      focused={focused}
      interactive={interactive}
      onOpenObject={interactive ? () => navigate(`/objects/${node.id}`) : undefined}
      onOpenUniverse={interactive ? () => navigate(`/lineage/universe/${node.id}`) : undefined}
      onActivate={activate}
      onSelectInLineage={activate}
    >
      {detail ? (
        <Typography.Text type="secondary" className="lineage-asset-chip__hint" ellipsis>
          {detail}
        </Typography.Text>
      ) : null}
    </LineageAssetChip>
  );
};

const Hop = ({
  row,
  dimmed,
  anchor = false,
  index = 0,
  selectedAssetId,
  inspectorAssetId,
  focusId,
  onFocusNode,
}: {
  row: FlowRow;
  dimmed: boolean;
  anchor?: boolean;
  index?: number;
  selectedAssetId?: string;
  inspectorAssetId?: string;
  focusId?: string | null;
  onFocusNode?: (assetId: string, anchorKey?: string) => void;
}) => (
  <div
    className={dimmed ? 'lineage-list-hop is-dimmed' : 'lineage-list-hop'}
    data-lineage-key={row.key}
    data-lineage-anchor={anchor ? 'true' : undefined}
    style={{ '--lineage-hop-i': index } as CSSProperties}
  >
    <NodeCard
      node={row.left}
      selected={row.left.id === selectedAssetId}
      inspected={row.left.id === inspectorAssetId}
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
          inspected={row.actor.id === inspectorAssetId}
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
      inspected={row.right.id === inspectorAssetId}
      focused={row.right.id === focusId}
      onFocusNode={onFocusNode ? (assetId) => onFocusNode(assetId, row.key) : undefined}
    />
  </div>
);

const ListRows = ({
  rows,
  rowsRef,
  clusterRef,
  anchorKey,
  dependencyKeys,
  selectedAssetId,
  inspectorAssetId,
  focusId,
  onFocusNode,
}: {
  rows: FlowRow[];
  rowsRef: { current: HTMLDivElement | null };
  clusterRef: { current: HTMLDivElement | null };
  anchorKey: string | null;
  dependencyKeys: Set<string>;
  selectedAssetId?: string;
  inspectorAssetId?: string;
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
  const hopProps = { selectedAssetId, inspectorAssetId, focusId, onFocusNode };
  const renderHop = (row: FlowRow, dimmed: boolean, index: number) => (
    <Hop
      key={row.key}
      row={row}
      dimmed={dimmed}
      index={index}
      anchor={row.key === anchorKey}
      {...hopProps}
    />
  );

  if (anchorIndex < 0) {
    return (
      <div className="lineage-list-rows" ref={rowsRef}>
        {rows.map((row, index) => renderHop(row, false, index))}
      </div>
    );
  }

  const before = rows.slice(0, clusterStart);
  const cluster = rows.slice(clusterStart, clusterEnd + 1);
  const after = rows.slice(clusterEnd + 1);
  return (
    <div className="lineage-list-rows" ref={rowsRef}>
      {before.map((row, index) => renderHop(row, !dependencyKeys.has(row.key), index))}
      <div className="lineage-list-focus" ref={clusterRef}>
        {cluster.map((row, index) =>
          renderHop(row, false, before.length + index)
        )}
      </div>
      {after.map((row, index) =>
        renderHop(row, !dependencyKeys.has(row.key), before.length + cluster.length + index)
      )}
    </div>
  );
};

const Arrow = ({ label }: { label: string }) => (
  <Tooltip title={label}>
    <span className="lineage-list-arrow">
      <span className="lineage-list-arrow__line" aria-hidden />
      <Typography.Text
        type="secondary"
        ellipsis
        className="lineage-list-arrow__label"
      >
        {label}
      </Typography.Text>
      <span className="lineage-list-arrow__head" aria-hidden>
        →
      </span>
    </span>
  </Tooltip>
);

const SCROLL_MS = 560;

const easeInOut = (t: number) => (t < 0.5 ? 4 * t * t * t : 1 - ((-2 * t + 2) ** 3) / 2);

const canScroll = (el: HTMLElement) => {
  const overflow = getComputedStyle(el).overflowY;
  return (overflow === 'auto' || overflow === 'scroll') && el.scrollHeight > el.clientHeight + 1;
};

const findScroller = (from: HTMLElement): HTMLElement | null => {
  const marked = from.closest('.lineage-list-scroll');
  if (marked instanceof HTMLElement && canScroll(marked)) {
    return marked;
  }
  let node: HTMLElement | null = from.parentElement;
  while (node) {
    if (canScroll(node)) {
      return node;
    }
    node = node.parentElement;
  }
  if (document.scrollingElement instanceof HTMLElement && canScroll(document.scrollingElement)) {
    return document.scrollingElement;
  }
  return marked instanceof HTMLElement ? marked : null;
};

const clusterDelta = (scroller: HTMLElement, cluster: HTMLElement): number => {
  const anchor = cluster.querySelector<HTMLElement>('[data-lineage-anchor="true"]') ?? cluster;
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
  return delta;
};

const LineageListView = ({
  nodes,
  edges,
  selectedAssetId,
  inspectorAssetId,
  focusId = null,
  focusAnchorKey = null,
  onFocusNode,
  rootsOverview = false,
}: Props) => {
  const clusterRef = useRef<HTMLDivElement>(null);
  const rowsRef = useRef<HTMLDivElement>(null);
  const scrollFrame = useRef<number | null>(null);
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

  useLayoutEffect(() => {
    const root = rowsRef.current;
    if (!root) {
      return;
    }
    const scroller = findScroller(root);
    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const delta =
      focusId && clusterRef.current && scroller ? clusterDelta(scroller, clusterRef.current) : 0;
    if (scrollFrame.current !== null) {
      cancelAnimationFrame(scrollFrame.current);
      scrollFrame.current = null;
    }
    if (!scroller || Math.abs(delta) < 1) {
      return;
    }
    if (reduceMotion) {
      scroller.scrollTop += delta;
      return;
    }
    const start = scroller.scrollTop;
    const started = performance.now();
    if (scrollFrame.current !== null) {
      cancelAnimationFrame(scrollFrame.current);
    }
    const step = (now: number) => {
      const t = Math.min(1, (now - started) / SCROLL_MS);
      scroller.scrollTop = start + delta * easeInOut(t);
      if (t < 1) {
        scrollFrame.current = requestAnimationFrame(step);
        return;
      }
      scrollFrame.current = null;
    };
    scrollFrame.current = requestAnimationFrame(step);
    return () => {
      if (scrollFrame.current !== null) {
        cancelAnimationFrame(scrollFrame.current);
        scrollFrame.current = null;
      }
    };
  }, [rows, focusId, focused.anchorKey]);

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
      <div className="lineage-list-view">
        <Space direction="vertical" size={16} style={{ width: '100%' }}>
          <Typography.Paragraph type="secondary" style={{ marginBottom: 0 }}>
            Выберите источник, чтобы посмотреть его связи.
          </Typography.Paragraph>
          {stages.map((type, stageIndex) => (
            <div
              key={type}
              className="lineage-list-stage"
              style={{ '--lineage-stage-i': stageIndex } as CSSProperties}
            >
              <Tag color={TYPE_COLOR[type]} className="lineage-list-stage__tag">
                {ASSET_TYPE_LABELS[type] ?? type}
              </Tag>
              <div className="lineage-list-stage__chips">
                {nodes
                  .filter((node) => node.asset_type === type)
                  .map((node, chipIndex) => (
                    <div
                      key={node.id}
                      className="lineage-list-chip-enter"
                      style={{ '--lineage-chip-i': chipIndex } as CSSProperties}
                    >
                      <NodeCard
                        node={node}
                        showType={false}
                        selected={node.id === selectedAssetId}
                        inspected={node.id === inspectorAssetId}
                        focused={node.id === focusId}
                        detail={
                          node.asset_type === 'DATA_SOURCE' &&
                          node.extraction_source_count != null
                            ? extractionSourcesLabel(node.extraction_source_count)
                            : null
                        }
                        onFocusNode={onFocusNode}
                      />
                    </div>
                  ))}
              </div>
            </div>
          ))}
        </Space>
      </div>
    );
  }
  if (!edges.length || !rows.length) {
    return (
      <Empty description="В доступных метаданных нет связей для этого объекта." />
    );
  }

  return (
    <div className="lineage-list-view">
      <Space direction="vertical" size={16} style={{ width: '100%' }}>
        <ListRows
          rows={rows}
          rowsRef={rowsRef}
          clusterRef={clusterRef}
          anchorKey={focused.anchorKey}
          dependencyKeys={focused.dependencyKeys}
          selectedAssetId={selectedAssetId}
          inspectorAssetId={inspectorAssetId}
          focusId={focusId}
          onFocusNode={onFocusNode}
        />
      </Space>
    </div>
  );
};

export default LineageListView;
