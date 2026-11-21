import type { LineageEdge, LineageNode } from '@shared/api/generated';
import { buildFlowEdges } from './lineageFlow';

export const inspectorConnections = (
    assetId: string,
    nodes: LineageNode[],
    edges: LineageEdge[]
) => {
    const byId = new Map(nodes.map((node) => [node.id, node]));
    const flowEdges = buildFlowEdges(nodes, edges);
    const neighbours = (direction: 'incoming' | 'outgoing') => flowEdges.flatMap((edge) => {
        const matches = direction === 'incoming' ? edge.target === assetId : edge.source === assetId;
        if (!matches) return [];
        const node = byId.get(direction === 'incoming' ? edge.source : edge.target);
        return node ? [{ edge, node }] : [];
    });
    return { incoming: neighbours('incoming'), outgoing: neighbours('outgoing') };
};
