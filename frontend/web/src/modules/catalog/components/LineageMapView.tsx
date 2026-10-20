import type { LineageEdge, LineageNode } from '@shared/api/generated';
import {
  Background,
  Controls,
  MarkerType,
  MiniMap,
  ReactFlow,
  type Edge,
  type Node,
  type NodeProps,
  type ReactFlowInstance,
  Handle,
  Position,
} from '@xyflow/react';
import { Empty } from 'antd';
import { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import '@xyflow/react/dist/style.css';
import LineageAssetChip from './LineageAssetChip';
import {
  LINEAGE_NODE_HEIGHT,
  LINEAGE_NODE_WIDTH,
  TYPE_ACCENT,
  buildFlowEdges,
  layoutLineageMap,
} from './lineageFlow';
import './lineageViews.css';

type Props = {
  nodes: LineageNode[];
  edges: LineageEdge[];
  selectedAssetId?: string;
  focusId?: string | null;
  onFocusNode?: (assetId: string) => void;
  onClearFocus?: () => void;
  rootsOverview?: boolean;
};

type AssetNodeData = {
  label: string;
  assetType: string;
  unresolved?: boolean;
  accent: string;
  selected?: boolean;
  focused?: boolean;
  onOpenObject?: () => void;
  onFocusNode?: () => void;
};

type AssetFlowNode = Node<AssetNodeData, 'asset'>;

const AssetFlowNodeView = ({ data }: NodeProps<AssetFlowNode>) => (
  <>
    <Handle type="target" position={Position.Left} style={{ opacity: 0.35 }} />
    <LineageAssetChip
      assetType={data.assetType}
      title={data.label}
      unresolved={data.unresolved}
      selected={data.selected}
      focused={data.focused}
      interactive={!data.unresolved}
      onOpenObject={data.onOpenObject}
      onActivate={data.onFocusNode}
      onSelectInLineage={data.onFocusNode}
    />
    <Handle type="source" position={Position.Right} style={{ opacity: 0.35 }} />
  </>
);

const nodeTypes = { asset: AssetFlowNodeView };

const frameNeighborhood = (
  instance: ReactFlowInstance<AssetFlowNode, Edge>,
  container: HTMLElement,
  focusId: string,
  neighborhood: AssetFlowNode[]
) => {
  const focusNode = neighborhood.find((node) => node.id === focusId);
  if (!focusNode || container.clientWidth < 40 || container.clientHeight < 40 || !neighborhood.length) {
    return;
  }
  const padding = 32;
  const width = container.clientWidth;
  const height = container.clientHeight;
  const minX = Math.min(...neighborhood.map((node) => node.position.x));
  const minY = Math.min(...neighborhood.map((node) => node.position.y));
  const maxX = Math.max(...neighborhood.map((node) => node.position.x + LINEAGE_NODE_WIDTH));
  const maxY = Math.max(...neighborhood.map((node) => node.position.y + LINEAGE_NODE_HEIGHT));
  const bounds = { x: minX, y: minY, width: Math.max(maxX - minX, 1), height: Math.max(maxY - minY, 1) };
  const current = instance.getViewport();
  const fitZoom = Math.min(
    (width - padding * 2) / Math.max(bounds.width, 1),
    (height - padding * 2) / Math.max(bounds.height, 1)
  );
  const zoom = Math.min(1, Math.max(0.2, fitZoom));
  const screenX = focusNode.position.x * current.zoom + current.x;
  const screenY = focusNode.position.y * current.zoom + current.y;
  let x = screenX - focusNode.position.x * zoom;
  let y = screenY - focusNode.position.y * zoom;
  const left = bounds.x * zoom + x;
  const top = bounds.y * zoom + y;
  const right = left + bounds.width * zoom;
  const bottom = top + bounds.height * zoom;
  if (left < padding) {
    x += padding - left;
  } else if (right > width - padding) {
    x -= right - (width - padding);
  }
  if (top < padding) {
    y += padding - top;
  } else if (bottom > height - padding) {
    y -= bottom - (height - padding);
  }
  void instance.setViewport({ x, y, zoom }, { duration: 280 });
};

const LineageMapView = ({
  nodes,
  edges,
  selectedAssetId,
  focusId = null,
  onFocusNode,
  onClearFocus,
  rootsOverview = false,
}: Props) => {
  const navigate = useNavigate();
  const containerRef = useRef<HTMLDivElement>(null);
  const [instance, setInstance] = useState<ReactFlowInstance<AssetFlowNode, Edge> | null>(null);
  const focusRef = useRef(onFocusNode);
  focusRef.current = onFocusNode;
  const clearRef = useRef(onClearFocus);
  clearRef.current = onClearFocus;

  const flow = useMemo(() => {
    if (!nodes.length) {
      return {
        nodes: [] as AssetFlowNode[],
        edges: [] as Edge[],
        neighborhoodIds: [] as string[],
      };
    }
    const flowEdges = edges.length ? buildFlowEdges(nodes, edges) : [];
    const links = flowEdges.map((edge) => ({ from: edge.source, to: edge.target }));
    const layout = layoutLineageMap(nodes, links, focusId);
    const rfNodes: AssetFlowNode[] = nodes.map((node) => {
      const position = layout.positions.get(node.id) ?? { x: 0, y: 0 };
      const inNeighborhood = !focusId || layout.neighborhood.has(node.id);
      return {
        id: node.id,
        type: 'asset',
        position,
        width: LINEAGE_NODE_WIDTH,
        height: LINEAGE_NODE_HEIGHT,
        zIndex: node.id === focusId ? 3 : inNeighborhood ? 2 : 1,
        style: { opacity: inNeighborhood ? 1 : 0.28 },
        data: {
          label: node.display_name,
          assetType: node.asset_type,
          unresolved: node.unresolved,
          accent: TYPE_ACCENT[node.asset_type] || '#8c8c8c',
          selected: node.id === selectedAssetId,
          focused: node.id === focusId,
          onOpenObject: node.unresolved
            ? undefined
            : () => {
                navigate(`/objects/${node.id}`);
              },
          onFocusNode:
            node.unresolved || !focusRef.current
              ? undefined
              : () => {
                  focusRef.current?.(node.id);
                },
        },
      };
    });
    const rfEdges: Edge[] = flowEdges.map((edge) => {
      const related =
        !focusId || (layout.neighborhood.has(edge.source) && layout.neighborhood.has(edge.target));
      return {
        id: edge.id,
        source: edge.source,
        target: edge.target,
        label: edge.label,
        markerEnd: { type: MarkerType.ArrowClosed, width: 16, height: 16 },
        style: {
          stroke: related && focusId ? '#1677ff' : '#8c8c8c',
          opacity: related ? 1 : 0.12,
        },
        labelStyle: { fontSize: 11, fill: '#595959' },
        labelBgStyle: { fill: '#fafafa' },
        labelBgPadding: [4, 6] as [number, number],
        labelBgBorderRadius: 4,
      };
    });
    return {
      nodes: rfNodes,
      edges: rfEdges,
      neighborhoodIds: focusId ? [...layout.neighborhood] : [],
    };
  }, [nodes, edges, focusId, selectedAssetId, navigate]);

  const graphKey = `${nodes.map((node) => node.id).join('|')}::${edges.map((edge) => edge.id).join('|')}`;
  const neighborhoodKey = flow.neighborhoodIds.join('|');
  const neighborhoodRef = useRef<AssetFlowNode[]>([]);
  neighborhoodRef.current = flow.nodes.filter((node) => flow.neighborhoodIds.includes(node.id));
  const graphKeyRef = useRef('');

  useEffect(() => {
    const container = containerRef.current;
    if (!instance || !container) {
      return;
    }
    const graphChanged = graphKeyRef.current !== graphKey;
    graphKeyRef.current = graphKey;
    let lastWidth = container.clientWidth;
    const apply = (allowFitAll: boolean) => {
      if (container.clientWidth < 40 || container.clientHeight < 40) {
        return;
      }
      if (focusId && neighborhoodRef.current.length) {
        frameNeighborhood(instance, container, focusId, neighborhoodRef.current);
        return;
      }
      if (!focusId && allowFitAll) {
        void instance.fitView({ padding: 0.2, duration: 200 });
      }
    };
    const frame = requestAnimationFrame(() => apply(graphChanged));
    const observer = new ResizeObserver(() => {
      const width = container.clientWidth;
      const shown = lastWidth < 40 && width >= 40;
      lastWidth = width;
      if (shown) {
        apply(true);
      }
    });
    observer.observe(container);
    return () => {
      cancelAnimationFrame(frame);
      observer.disconnect();
    };
  }, [instance, graphKey, focusId, neighborhoodKey]);

  if (!nodes.length) {
    return (
      <Empty
        description={
          rootsOverview ? 'Нет корневых объектов lineage' : 'Нет lineage для выбранного объекта'
        }
      />
    );
  }
  if (!rootsOverview && (!edges.length || !flow.edges.length)) {
    return <Empty description="У объекта нет data-flow рёбер для карты зависимостей." />;
  }

  return (
    <div
      ref={containerRef}
      style={{
        flex: 1,
        minHeight: 0,
        height: '100%',
        width: '100%',
        border: '1px solid #f0f0f0',
        borderRadius: 8,
        overflow: 'hidden',
      }}
    >
      <ReactFlow
        nodes={flow.nodes}
        edges={flow.edges}
        nodeTypes={nodeTypes}
        onInit={setInstance}
        onPaneClick={() => clearRef.current?.()}
        minZoom={0.2}
        maxZoom={1.5}
        nodesDraggable={false}
        nodesConnectable={false}
        elementsSelectable
        style={{ width: '100%', height: '100%' }}
      >
        <Background gap={16} color="#f0f0f0" />
        <Controls showInteractive={false} />
        <MiniMap
          pannable
          zoomable
          nodeColor={(node) => (node.data as AssetNodeData).accent || '#8c8c8c'}
        />
      </ReactFlow>
    </div>
  );
};

export default LineageMapView;
