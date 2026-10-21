import type { LineageEdge, LineageNode } from '@shared/api/generated';
import {
  Background,
  Controls,
  MarkerType,
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
type WaypointNode = Node<{ kind: 'waypoint' }, 'waypoint'>;
type MapNode = AssetFlowNode | WaypointNode;

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

const WaypointView = () => (
  <>
    <Handle type="target" position={Position.Left} style={{ opacity: 0, width: 1, height: 1, border: 'none' }} />
    <Handle type="source" position={Position.Right} style={{ opacity: 0, width: 1, height: 1, border: 'none' }} />
  </>
);

const nodeTypes = { asset: AssetFlowNodeView, waypoint: WaypointView };

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
  const [instance, setInstance] = useState<ReactFlowInstance<MapNode, Edge> | null>(null);
  const [hoveredEdgeId, setHoveredEdgeId] = useState<string | null>(null);
  const focusRef = useRef(onFocusNode);
  focusRef.current = onFocusNode;
  const clearRef = useRef(onClearFocus);
  clearRef.current = onClearFocus;
  const centerId = rootsOverview ? null : (focusId ?? selectedAssetId ?? null);

  const flow = useMemo(() => {
    if (!nodes.length) {
      return {
        nodes: [] as MapNode[],
        edges: [] as Array<
          Edge & { caption: string; incident: boolean; groupId: string; arrow: boolean }
        >,
        neighborhoodKey: '',
      };
    }
    const flowEdges = edges.length ? buildFlowEdges(nodes, edges) : [];
    const links = flowEdges.map((edge) => ({
      from: edge.source,
      to: edge.target,
      id: edge.id,
      label: edge.label,
    }));
    const layout = layoutLineageMap(nodes, links, centerId);
    const rfNodes: MapNode[] = [];
    for (const node of nodes) {
      const position = layout.positions.get(node.id);
      if (!position) {
        continue;
      }
      rfNodes.push({
        id: node.id,
        type: 'asset',
        position,
        width: LINEAGE_NODE_WIDTH,
        height: LINEAGE_NODE_HEIGHT,
        zIndex: node.id === centerId ? 3 : 2,
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
      });
    }
    for (const [id, position] of layout.waypoints) {
      rfNodes.push({
        id,
        type: 'waypoint',
        position,
        width: 8,
        height: 8,
        selectable: false,
        draggable: false,
        connectable: false,
        focusable: false,
        data: { kind: 'waypoint' },
        style: { opacity: 0, pointerEvents: 'none', width: 8, height: 8 },
      });
    }
    const routed = layout.segments.length
      ? layout.segments.map((segment) => ({
          id: segment.id,
          source: segment.source,
          target: segment.target,
          caption: segment.label,
          incident: segment.incident,
          groupId: segment.groupId,
          arrow: segment.arrow,
        }))
      : flowEdges.flatMap((edge) => {
          if (!layout.neighborhood.has(edge.source) || !layout.neighborhood.has(edge.target)) {
            return [];
          }
          return [
            {
              id: edge.id,
              source: edge.source,
              target: edge.target,
              caption: edge.label,
              incident: edge.source === centerId || edge.target === centerId,
              groupId: edge.id,
              arrow: true,
            },
          ];
        });
    const rfEdges = routed.map((edge) => ({
      id: edge.id,
      source: edge.source,
      target: edge.target,
      type: 'smoothstep' as const,
      pathOptions: { borderRadius: 4 },
      caption: edge.caption,
      incident: edge.incident,
      groupId: edge.groupId,
      arrow: edge.arrow,
      data: { groupId: edge.groupId },
      interactionWidth: 16,
      markerEnd: edge.arrow ? { type: MarkerType.ArrowClosed, width: 16, height: 16 } : undefined,
      labelStyle: { fontSize: 11, fill: '#595959' },
      labelBgStyle: { fill: '#fafafa' },
      labelBgPadding: [4, 6] as [number, number],
      labelBgBorderRadius: 4,
    }));
    const neighborhoodKey = [...layout.neighborhood].sort().join('|');
    return { nodes: rfNodes, edges: rfEdges, neighborhoodKey };
  }, [nodes, edges, centerId, focusId, selectedAssetId, navigate]);

  const visibleEdges = useMemo(
    () =>
      flow.edges.map((edge) => {
        const active = edge.incident || edge.groupId === hoveredEdgeId;
        const stroke = active ? '#1677ff' : '#bfbfbf';
        return {
          ...edge,
          label: edge.groupId === hoveredEdgeId && edge.caption ? edge.caption : undefined,
          style: { stroke, strokeWidth: active ? 1.6 : 1 },
          markerEnd: edge.arrow
            ? { type: MarkerType.ArrowClosed, width: 16, height: 16, color: stroke }
            : undefined,
        };
      }),
    [flow.edges, hoveredEdgeId]
  );

  useEffect(() => {
    const container = containerRef.current;
    if (!instance || !container) {
      return;
    }
    let lastWidth = container.clientWidth;
    const apply = () => {
      if (container.clientWidth < 40 || container.clientHeight < 40 || !flow.nodes.length) {
        return;
      }
      void instance.fitView({ padding: 0.22, duration: 520, maxZoom: 1 });
    };
    const frame = requestAnimationFrame(apply);
    const observer = new ResizeObserver(() => {
      const width = container.clientWidth;
      const shown = lastWidth < 40 && width >= 40;
      lastWidth = width;
      if (shown) {
        apply();
      }
    });
    observer.observe(container);
    return () => {
      cancelAnimationFrame(frame);
      observer.disconnect();
    };
  }, [instance, flow.neighborhoodKey, flow.nodes.length]);

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
        edges={visibleEdges}
        nodeTypes={nodeTypes}
        onInit={setInstance}
        onPaneClick={() => clearRef.current?.()}
        onEdgeMouseEnter={(_event, edge) => {
          const data = edge.data as { groupId?: string } | undefined;
          setHoveredEdgeId(data?.groupId ?? edge.id);
        }}
        onEdgeMouseLeave={() => setHoveredEdgeId(null)}
        onlyRenderVisibleElements
        minZoom={0.2}
        maxZoom={1.5}
        nodesDraggable={false}
        nodesConnectable={false}
        elementsSelectable
        style={{ width: '100%', height: '100%' }}
      >
        <Background gap={16} color="#f0f0f0" />
        <Controls showInteractive={false} />
      </ReactFlow>
    </div>
  );
};

export default LineageMapView;
