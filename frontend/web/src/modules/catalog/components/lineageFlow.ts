import type { LineageEdge, LineageNode } from '@shared/api/generated';

export const TYPE_COLOR: Record<string, string> = {
  DATA_SOURCE: 'purple',
  EXTRACTION_SOURCE: 'blue',
  STORAGE_LOCATION: 'gold',
  PROCESS: 'cyan',
  TABLE: 'green',
  VIEW: 'green',
  MATERIALIZED_VIEW: 'green',
};

/** Hex fills for React Flow nodes (aligned with Ant Tag colors). */
export const TYPE_FILL: Record<string, string> = {
  DATA_SOURCE: '#722ed1',
  EXTRACTION_SOURCE: '#1677ff',
  STORAGE_LOCATION: '#faad14',
  PROCESS: '#13c2c2',
  TABLE: '#52c41a',
  VIEW: '#389e0d',
  MATERIALIZED_VIEW: '#237804',
};

export const STAGE_ORDER = [
  'DATA_SOURCE',
  'EXTRACTION_SOURCE',
  'STORAGE_LOCATION',
  'PROCESS',
  'TABLE',
  'VIEW',
  'MATERIALIZED_VIEW',
];

/** Edge types stored against data-flow; flip for left→right display. */
export const FLIP_FOR_FLOW = new Set(['READS_FROM', 'DERIVED_FROM']);

export type FlowRow = {
  key: string;
  left: LineageNode;
  actor?: LineageNode;
  right: LineageNode;
  flowLabel: string;
};

export const flowEndpoints = (
  edge: LineageEdge,
  byId: Map<string, LineageNode>
): { left: LineageNode; right: LineageNode } | null => {
  const from = byId.get(edge.from_asset_id);
  const to = byId.get(edge.to_asset_id);
  if (!from || !to) {
    return null;
  }
  if (FLIP_FOR_FLOW.has(edge.relationship_type)) {
    return { left: to, right: from };
  }
  return { left: from, right: to };
};

export const flowLabelFor = (
  relationshipType: string,
  leftType?: string,
  rightType?: string
): string => {
  if (
    relationshipType === 'EXTRACTS_TO' &&
    leftType === 'DATA_SOURCE' &&
    rightType === 'EXTRACTION_SOURCE'
  ) {
    return 'предоставляет';
  }
  switch (relationshipType) {
    case 'DERIVED_FROM':
      return 'порождает';
    case 'READS_FROM':
      return 'питает';
    case 'WRITES_TO':
      return 'пишет';
    case 'EXTRACTS_TO':
      return 'извлекает';
    default:
      return relationshipType.toLowerCase();
  }
};

/**
 * Left→right data-flow rows for the list view.
 * PROCESS sits in the middle when both READS_FROM and WRITES_TO exist.
 */
export const buildFlowRows = (nodes: LineageNode[], edges: LineageEdge[]): FlowRow[] => {
  const byId = new Map(nodes.map((node) => [node.id, node]));
  const consumed = new Set<string>();
  const rows: FlowRow[] = [];

  const processes = nodes.filter((node) => node.asset_type === 'PROCESS');
  for (const process of processes) {
    const reads = edges.filter(
      (edge) => edge.relationship_type === 'READS_FROM' && edge.from_asset_id === process.id
    );
    const writes = edges.filter(
      (edge) => edge.relationship_type === 'WRITES_TO' && edge.from_asset_id === process.id
    );
    if (!writes.length) {
      continue;
    }
    const sources = reads
      .map((edge) => byId.get(edge.to_asset_id))
      .filter((node): node is LineageNode => Boolean(node));
    const lefts = sources.length ? sources : [null];
    for (const write of writes) {
      const target = byId.get(write.to_asset_id);
      if (!target) {
        continue;
      }
      consumed.add(write.id);
      for (const read of reads) {
        consumed.add(read.id);
      }
      for (const left of lefts) {
        if (left) {
          rows.push({
            key: `${process.id}:${left.id}:${target.id}:${write.id}`,
            left,
            actor: process,
            right: target,
            flowLabel: 'загружает',
          });
        } else {
          rows.push({
            key: `${process.id}::${target.id}:${write.id}`,
            left: process,
            right: target,
            flowLabel: 'пишет',
          });
        }
      }
    }
  }

  for (const edge of edges) {
    if (consumed.has(edge.id)) {
      continue;
    }
    const ends = flowEndpoints(edge, byId);
    if (!ends) {
      continue;
    }
    if (edge.relationship_type === 'READS_FROM') {
      const process = byId.get(edge.from_asset_id);
      if (process?.asset_type === 'PROCESS' && rows.some((row) => row.actor?.id === process.id)) {
        continue;
      }
    }
    rows.push({
      key: edge.id,
      left: ends.left,
      right: ends.right,
      flowLabel: flowLabelFor(edge.relationship_type, ends.left.asset_type, ends.right.asset_type),
    });
  }

  const stageRank = (type: string) => {
    const index = STAGE_ORDER.indexOf(type);
    return index < 0 ? 99 : index;
  };
  rows.sort((a, b) => {
    const leftDiff = stageRank(a.left.asset_type) - stageRank(b.left.asset_type);
    if (leftDiff !== 0) {
      return leftDiff;
    }
    return a.left.display_name.localeCompare(b.left.display_name);
  });
  return rows;
};

/** Normalized flow edges for the map (always left→right data direction). */
export const buildFlowEdges = (
  nodes: LineageNode[],
  edges: LineageEdge[]
): Array<{ id: string; source: string; target: string; label: string; relationshipType: string }> => {
  const byId = new Map(nodes.map((node) => [node.id, node]));
  const result: Array<{
    id: string;
    source: string;
    target: string;
    label: string;
    relationshipType: string;
  }> = [];
  for (const edge of edges) {
    const ends = flowEndpoints(edge, byId);
    if (!ends) {
      continue;
    }
    result.push({
      id: edge.id,
      source: ends.left.id,
      target: ends.right.id,
      label: flowLabelFor(edge.relationship_type, ends.left.asset_type, ends.right.asset_type),
      relationshipType: edge.relationship_type,
    });
  }
  return result;
};
