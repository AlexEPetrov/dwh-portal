import { ExtensionCategory, Graph, register, type GraphOptions } from '@antv/g6';
import { ReactNode } from '@antv/g6-extension-react';
import { useThemeMode } from '@asset-management/app-shell/theme';
import type { LineageEdge, LineageNode } from '@shared/api/generated';
import { Empty } from 'antd';
import { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import LineageAssetChip from './LineageAssetChip';
import {
  LINEAGE_NODE_HEIGHT,
  LINEAGE_NODE_WIDTH,
  buildFlowEdges,
  originCaption,
} from './lineageFlow';
import './lineageViews.css';

/**
 * React Flow draws each edge on its own curve and does not keep dagre bend points,
 * so a lineage chain crosses itself. G6's antv-dagre writes those points and the
 * polyline follows them, one rank at a time, left to right.
 */
register(ExtensionCategory.NODE, 'lineage-asset', ReactNode);

type Props = {
  nodes: LineageNode[];
  edges: LineageEdge[];
  selectedAssetId?: string;
  inspectorAssetId?: string;
  focusId?: string | null;
  onFocusNode?: (assetId: string) => void;
  onClearFocus?: () => void;
  rootsOverview?: boolean;
};

type NodePayload = {
  label: string;
  assetType: string;
  hint: string | null;
  unresolved?: boolean;
  selected: boolean;
  focused: boolean;
  inspected: boolean;
};

type NodeDatum = {
  id: string;
  data?: NodePayload;
};

/** Short camera ease for toolbar zoom / focus pan. Fit-to-page always snaps. */
const FOCUS_MOTION = { duration: 240, easing: 'cubic-bezier(0.33, 1, 0.32, 1)' };
const ZOOM_STEP = { duration: 220, easing: 'cubic-bezier(0.33, 1, 0.32, 1)' };
const MIN_SURFACE = 40;

const surfaceReady = (el: HTMLElement | null) =>
  Boolean(el && el.clientWidth >= MIN_SURFACE && el.clientHeight >= MIN_SURFACE);

const LineageMapView = ({
  nodes,
  edges,
  selectedAssetId,
  inspectorAssetId,
  focusId = null,
  onFocusNode,
  onClearFocus,
  rootsOverview = false,
}: Props) => {
  const navigate = useNavigate();
  const { resolvedMode } = useThemeMode();
  const dark = resolvedMode === 'dark';
  const containerRef = useRef<HTMLDivElement>(null);
  const graphRef = useRef<Graph | null>(null);
  const drawQueue = useRef(Promise.resolve());
  const focusRef = useRef(onFocusNode);
  focusRef.current = onFocusNode;
  const clearRef = useRef(onClearFocus);
  clearRef.current = onClearFocus;
  const navigateRef = useRef(navigate);
  navigateRef.current = navigate;
  /** Clicked asset, else the page route asset — highlight only, not a second camera pass. */
  const centerId = rootsOverview ? null : (focusId ?? selectedAssetId ?? null);
  const topologyKey = useMemo(
    () =>
      `${nodes.map((node) => node.id).join(',')}|${edges.map((edge) => edge.id).join(',')}`,
    [nodes, edges]
  );
  const framedTopology = useRef<string | null>(null);
  const lastSurfaceSize = useRef({ w: 0, h: 0 });
  const [surfaceReadyToShow, setSurfaceReadyToShow] = useState(false);

  const model = useMemo(() => {
    // Same payload as the list: every node and data-flow edge from the API response.
    const flowEdges = edges.length ? buildFlowEdges(nodes, edges) : [];
    const layout: GraphOptions['layout'] = flowEdges.length
      ? {
          type: 'antv-dagre',
          rankdir: 'LR',
          align: 'UL',
          nodesep: 28,
          ranksep: 76,
          controlPoints: true,
          ranker: 'network-simplex',
          nodeSize: [LINEAGE_NODE_WIDTH, LINEAGE_NODE_HEIGHT],
          edgeLabelSpace: false,
        }
      : {
          type: 'grid',
          cols: Math.max(1, Math.ceil(Math.sqrt(nodes.length || 1))),
          nodeSize: [LINEAGE_NODE_WIDTH, LINEAGE_NODE_HEIGHT],
          condense: true,
        };
    return {
      nodes: nodes.map((node) => ({
        id: node.id,
        data: {
          label: node.display_name,
          assetType: node.asset_type,
          hint: originCaption(node.qualified_name),
          unresolved: node.unresolved,
          selected: node.id === selectedAssetId,
          focused: node.id === focusId,
          inspected: node.id === inspectorAssetId,
        } satisfies NodePayload,
      })),
      edges: flowEdges.map((edge) => ({
        id: edge.id,
        source: edge.source,
        target: edge.target,
        data: {
          label: edge.label,
          incident: Boolean(centerId && (edge.source === centerId || edge.target === centerId)),
        },
      })),
      layout,
    };
  }, [nodes, edges, centerId, selectedAssetId, inspectorAssetId, focusId]);

  const active = nodes.length > 0 && (rootsOverview || model.edges.length > 0);
  const modelRef = useRef(model);
  modelRef.current = model;

  const frameGraph = async (graph: Graph) => {
    const container = containerRef.current;
    if (!surfaceReady(container) || graph.destroyed) {
      return;
    }
    graph.resize();
    // Snap — animated fit is what showed the oversized frame first.
    await graph.fitView({ when: 'always', direction: 'both' }, false);
  };

  const easeToNode = async (graph: Graph, nodeId: string | null) => {
    if (!nodeId || graph.destroyed || !graph.getNodeData(nodeId)) {
      return;
    }
    await graph.focusElement(nodeId, FOCUS_MOTION);
  };

  useEffect(() => {
    if (!active) {
      return;
    }
    const container = containerRef.current;
    if (!container) {
      return;
    }

    let cancelled = false;
    let created: Graph | null = null;

    const build = () => {
      if (cancelled || graphRef.current || !surfaceReady(container)) {
        return;
      }
      const initial = modelRef.current;
      const instance = new Graph({
        container,
        width: container.clientWidth,
        height: container.clientHeight,
        autoResize: true,
        padding: 36,
        // Layout/node tween from the origin reads as a drift to the corner.
        animation: false,
        zoomRange: [0.2, 1.5],
        data: { nodes: initial.nodes, edges: initial.edges },
        layout: initial.layout,
        node: {
          type: 'lineage-asset',
          style: {
            size: [LINEAGE_NODE_WIDTH, LINEAGE_NODE_HEIGHT],
            dx: -LINEAGE_NODE_WIDTH / 2,
            dy: -LINEAGE_NODE_HEIGHT / 2,
            ports: [
              { key: 'left', placement: 'left' },
              { key: 'right', placement: 'right' },
            ],
            component: ((datum: NodeDatum) => {
              const payload = datum.data;
              const interactive = Boolean(payload && !payload.unresolved);
              const focus = () => focusRef.current?.(datum.id);
              return (
                <div
                  className="lineage-map-node"
                  onClick={(event) => event.stopPropagation()}
                  onPointerDown={(event) => event.stopPropagation()}
                >
                  <LineageAssetChip
                    assetType={payload?.assetType || ''}
                    title={payload?.label || ''}
                    hint={payload?.hint}
                    unresolved={payload?.unresolved}
                    selected={payload?.selected}
                    focused={payload?.focused}
                    inspected={payload?.inspected}
                    interactive={interactive}
                    onOpenObject={
                      interactive ? () => navigateRef.current(`/objects/${datum.id}`) : undefined
                    }
                    onOpenUniverse={
                      interactive
                        ? () => navigateRef.current(`/lineage/universe/${datum.id}`)
                        : undefined
                    }
                    onActivate={interactive ? focus : undefined}
                    onSelectInLineage={interactive ? focus : undefined}
                  />
                </div>
              );
            }) as never,
          },
        },
        edge: {
          type: 'polyline',
          style: {
            stroke: (datum: { data?: { incident?: boolean } }) =>
              datum.data?.incident ? '#3b82f6' : dark ? '#64748b' : '#b7b7b7',
            lineWidth: (datum: { data?: { incident?: boolean } }) =>
              datum.data?.incident ? 1.8 : 1.15,
            radius: 12,
            endArrow: true,
            endArrowType: 'vee',
            endArrowSize: 8,
            router: false,
            labelFontSize: 11,
            labelFill: dark ? '#e2e8f0' : '#434343',
            labelBackground: true,
            labelBackgroundFill: dark ? '#1e293b' : '#ffffff',
            labelBackgroundOpacity: 0.96,
            labelPadding: [4, 8],
            labelBackgroundRadius: 6,
            labelAutoRotate: false,
            labelOffsetY: -12,
            labelText: '',
          },
          state: {
            active: {
              stroke: '#1677ff',
              lineWidth: 2,
              labelText: (datum: { data?: { label?: string } }) => datum.data?.label ?? '',
            },
          },
        },
        behaviors: [
          'drag-canvas',
          // Instant wheel zoom — animated wheel stacks with fitView and feels floaty.
          'zoom-canvas',
          { type: 'hover-activate', degree: 0, state: 'active' },
        ],
        plugins: [
          {
            type: 'grid-line',
            // Light hairline in light mode; muted slate in dark (never near-white).
            stroke: dark ? 'rgba(148, 163, 184, 0.14)' : '#edf0f5',
            size: 20,
            follow: { translate: true, zoom: false },
            border: false,
          },
          {
            type: 'toolbar',
            position: 'bottom-right',
            className: 'lineage-map-toolbar',
            getItems: () => [
              { id: 'zoom-in', value: 'zoom-in', title: 'Ближе' },
              { id: 'zoom-out', value: 'zoom-out', title: 'Дальше' },
              { id: 'auto-fit', value: 'auto-fit', title: 'Вписать' },
            ],
            onClick: (value: string) => {
              const current = graphRef.current;
              if (!current) {
                return;
              }
              if (value === 'zoom-in') {
                void current.zoomBy(1.16, ZOOM_STEP);
              } else if (value === 'zoom-out') {
                void current.zoomBy(0.86, ZOOM_STEP);
              } else if (value === 'auto-fit') {
                void frameGraph(current);
              }
            },
          },
        ],
      });
      created = instance;
      graphRef.current = instance;
      lastSurfaceSize.current = {
        w: container.clientWidth,
        h: container.clientHeight,
      };
      instance.on('canvas:click', () => clearRef.current?.());
      drawQueue.current = drawQueue.current.then(async () => {
        if (cancelled || graphRef.current !== instance) {
          return;
        }
        await instance.render();
        if (framedTopology.current !== topologyKey) {
          framedTopology.current = topologyKey;
          await frameGraph(instance);
        }
        if (!cancelled) {
          setSurfaceReadyToShow(true);
        }
      });
    };

    build();
    const observer = new ResizeObserver(() => {
      if (!graphRef.current) {
        build();
        return;
      }
      const current = graphRef.current;
      const w = container.clientWidth;
      const h = container.clientHeight;
      const wasCollapsed =
        lastSurfaceSize.current.w < MIN_SURFACE || lastSurfaceSize.current.h < MIN_SURFACE;
      lastSurfaceSize.current = { w, h };
      if (!surfaceReady(container)) {
        return;
      }
      drawQueue.current = drawQueue.current.then(async () => {
        if (cancelled || graphRef.current !== current) {
          return;
        }
        // Tab panes go to 0×0 while inactive; hide until snap-fit so List→Graph
        // does not flash the pre-fit canvas.
        if (wasCollapsed) {
          setSurfaceReadyToShow(false);
        }
        await frameGraph(current);
        if (!cancelled && wasCollapsed) {
          setSurfaceReadyToShow(true);
        }
      });
    });
    observer.observe(container);

    return () => {
      cancelled = true;
      observer.disconnect();
      created?.destroy();
      if (graphRef.current === created) {
        graphRef.current = null;
      }
      framedTopology.current = null;
      lastSurfaceSize.current = { w: 0, h: 0 };
      setSurfaceReadyToShow(false);
    };
  }, [active, dark]);

  useEffect(() => {
    const graph = graphRef.current;
    if (!graph || !active) {
      return;
    }
    let cancelled = false;
    drawQueue.current = drawQueue.current.then(async () => {
      if (cancelled || graphRef.current !== graph || !surfaceReady(containerRef.current)) {
        return;
      }
      const topologyChanged = framedTopology.current !== topologyKey;
      graph.setLayout(model.layout);
      graph.setData({ nodes: model.nodes, edges: model.edges });
      await graph.render();
      if (cancelled || graphRef.current !== graph) {
        return;
      }
      if (topologyChanged) {
        framedTopology.current = topologyKey;
        await frameGraph(graph);
        setSurfaceReadyToShow(true);
        return;
      }
      if (focusId) {
        await easeToNode(graph, focusId);
      }
    });
    return () => {
      cancelled = true;
    };
  }, [active, model, topologyKey, focusId]);

  if (!nodes.length) {
    return (
      <Empty
        description={
          rootsOverview ? 'Нет корневых объектов lineage' : 'Нет lineage для выбранного объекта'
        }
      />
    );
  }
  if (!rootsOverview && !model.edges.length) {
    return <Empty description="У объекта нет data-flow рёбер для карты зависимостей." />;
  }

  return (
    <div className={surfaceReadyToShow ? 'lineage-map-shell is-ready' : 'lineage-map-shell'}>
      <div ref={containerRef} className="lineage-map" />
    </div>
  );
};

export default LineageMapView;
