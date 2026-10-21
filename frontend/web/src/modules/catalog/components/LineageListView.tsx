import type { LineageEdge, LineageNode } from '@shared/api/generated';
import { Empty, Space, Tag, Tooltip, Typography } from 'antd';
import { useLayoutEffect, useMemo, useRef } from 'react';
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
    data-lineage-key={row.key}
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
  rowsRef,
  clusterRef,
  anchorKey,
  dependencyKeys,
  selectedAssetId,
  focusId,
  onFocusNode,
}: {
  rows: FlowRow[];
  rowsRef: { current: HTMLDivElement | null };
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
    return (
      <div className="lineage-list-rows" ref={rowsRef}>
        {rows.map((row) => renderHop(row, false))}
      </div>
    );
  }

  const before = rows.slice(0, clusterStart);
  const cluster = rows.slice(clusterStart, clusterEnd + 1);
  const after = rows.slice(clusterEnd + 1);
  return (
    <div className="lineage-list-rows" ref={rowsRef}>
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

const SCROLL_MS = 560;
const SCROLL_EASING = 'cubic-bezier(0.45, 0, 0.25, 1)';

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

const layoutTop = (el: HTMLElement, scroller: HTMLElement): number => {
  let y = 0;
  let node: HTMLElement | null = el;
  while (node && node !== scroller) {
    y += node.offsetTop;
    const parent: Element | null = node.offsetParent;
    if (!(parent instanceof HTMLElement) || (parent !== scroller && !scroller.contains(parent))) {
      return el.getBoundingClientRect().top - scroller.getBoundingClientRect().top + scroller.scrollTop;
    }
    node = parent;
  }
  return y;
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
  focusId = null,
  focusAnchorKey = null,
  onFocusNode,
  rootsOverview = false,
}: Props) => {
  const clusterRef = useRef<HTMLDivElement>(null);
  const rowsRef = useRef<HTMLDivElement>(null);
  const topsRef = useRef<Map<string, number>>(new Map());
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
    const hops = root.querySelectorAll<HTMLElement>('[data-lineage-key]');
    hops.forEach((el) => el.getAnimations().forEach((animation) => animation.cancel()));
    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const delta =
      focusId && clusterRef.current && scroller ? clusterDelta(scroller, clusterRef.current) : 0;
    if (scrollFrame.current !== null) {
      cancelAnimationFrame(scrollFrame.current);
      scrollFrame.current = null;
    }
    hops.forEach((el) => {
      const key = el.dataset.lineageKey;
      if (!key || !scroller) {
        return;
      }
      const next = layoutTop(el, scroller);
      const prev = topsRef.current.get(key);
      if (!reduceMotion && prev !== undefined && Math.abs(prev - next) > 1) {
        el.getAnimations().forEach((animation) => animation.cancel());
        el.animate(
          [{ transform: `translateY(${prev - next}px)` }, { transform: 'translateY(0)' }],
          { duration: SCROLL_MS, easing: SCROLL_EASING }
        );
      }
      topsRef.current.set(key, next);
    });
    const live = new Set([...hops].map((el) => el.dataset.lineageKey));
    for (const key of topsRef.current.keys()) {
      if (!live.has(key)) {
        topsRef.current.delete(key);
      }
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
        rowsRef={rowsRef}
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
