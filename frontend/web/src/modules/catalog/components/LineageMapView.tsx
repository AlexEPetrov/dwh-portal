import type { LineageEdge, LineageNode } from '@shared/api/generated';
import dagre from '@dagrejs/dagre';
import {
  Background,
  Controls,
  MarkerType,
  MiniMap,
  ReactFlow,
  type Edge,
  type Node,
  type NodeProps,
  Handle,
  Position,
} from '@xyflow/react';
import { Empty } from 'antd';
import { useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import '@xyflow/react/dist/style.css';
import LineageAssetChip from './LineageAssetChip';
import { STAGE_ORDER, TYPE_ACCENT, buildFlowEdges } from './lineageFlow';
import './lineageViews.css';

type Props = {
  nodes: LineageNode[];
  edges: LineageEdge[];
};

type AssetNodeData = {
  label: string;
  assetType: string;
  unresolved?: boolean;
  accent: string;
};

const NODE_WIDTH = 200;
const NODE_HEIGHT = 64;

const AssetFlowNode = ({ data }: NodeProps<Node<AssetNodeData>>) => (
  <>
    <Handle type="target" position={Position.Left} style={{ opacity: 0.35 }} />
    <LineageAssetChip
      assetType={data.assetType}
      title={data.label}
      unresolved={data.unresolved}
      interactive={!data.unresolved}
    />
    <Handle type="source" position={Position.Right} style={{ opacity: 0.35 }} />
  </>
);

const nodeTypes = { asset: AssetFlowNode };

const layoutWithDagre = (nodes: Node<AssetNodeData>[], edges: Edge[]): Node<AssetNodeData>[] => {
  const graph = new dagre.graphlib.Graph();
  graph.setDefaultEdgeLabel(() => ({}));
  graph.setGraph({ rankdir: 'LR', nodesep: 48, ranksep: 72, marginx: 24, marginy: 24 });

  for (const node of nodes) {
    graph.setNode(node.id, { width: NODE_WIDTH, height: NODE_HEIGHT });
  }
  for (const edge of edges) {
    graph.setEdge(edge.source, edge.target);
  }
  dagre.layout(graph);

  return nodes.map((node) => {
    const pos = graph.node(node.id);
    return {
      ...node,
      position: {
        x: pos.x - NODE_WIDTH / 2,
        y: pos.y - NODE_HEIGHT / 2,
      },
      sourcePosition: Position.Right,
      targetPosition: Position.Left,
    };
  });
};

const LineageMapView = ({ nodes, edges }: Props) => {
  const navigate = useNavigate();
  const flow = useMemo(() => {
    if (!nodes.length || !edges.length) {
      return { nodes: [] as Node<AssetNodeData>[], edges: [] as Edge[] };
    }
    const flowEdges = buildFlowEdges(nodes, edges);
    const rfNodes: Node<AssetNodeData>[] = nodes.map((node) => ({
      id: node.id,
      type: 'asset',
      position: { x: 0, y: 0 },
      data: {
        label: node.display_name,
        assetType: node.asset_type,
        unresolved: node.unresolved,
        accent: TYPE_ACCENT[node.asset_type] || '#8c8c8c',
      },
    }));
    rfNodes.sort((a, b) => {
      const stageDiff =
        STAGE_ORDER.indexOf(a.data.assetType) - STAGE_ORDER.indexOf(b.data.assetType);
      if (stageDiff !== 0) {
        return stageDiff;
      }
      return a.data.label.localeCompare(b.data.label);
    });
    const rfEdges: Edge[] = flowEdges.map((edge) => ({
      id: edge.id,
      source: edge.source,
      target: edge.target,
      label: edge.label,
      markerEnd: { type: MarkerType.ArrowClosed, width: 16, height: 16 },
      style: { stroke: '#8c8c8c' },
      labelStyle: { fontSize: 11, fill: '#595959' },
      labelBgStyle: { fill: '#fafafa' },
      labelBgPadding: [4, 6] as [number, number],
      labelBgBorderRadius: 4,
    }));
    return {
      nodes: layoutWithDagre(rfNodes, rfEdges),
      edges: rfEdges,
    };
  }, [nodes, edges]);

  if (!nodes.length) {
    return <Empty description="Нет lineage для выбранного объекта" />;
  }
  if (!edges.length || !flow.edges.length) {
    return <Empty description="У объекта нет data-flow рёбер для карты зависимостей." />;
  }

  return (
    <div
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
        fitView
        fitViewOptions={{ padding: 0.2 }}
        minZoom={0.2}
        maxZoom={1.5}
        nodesDraggable
        nodesConnectable={false}
        elementsSelectable
        style={{ width: '100%', height: '100%' }}
        onNodeClick={(_, node) => {
          const asset = nodes.find((item) => item.id === node.id);
          if (asset && !asset.unresolved) {
            navigate(`/objects/${asset.id}`);
          }
        }}
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
