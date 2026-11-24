import type { LineageEdge, LineageNode } from '@shared/api/generated';

/** Scroll the nearest edge of a selected item into a viewport. */
export const revealOffset = (
  start: number, end: number, viewportStart: number, viewportEnd: number,
): number => {
  if (start < viewportStart) return start - viewportStart;
  if (end > viewportEnd) return end - viewportEnd;
  return 0;
};

export const TYPE_COLOR: Record<string, string> = {
  DATA_SOURCE: 'purple',
  EXTRACTION_SOURCE: 'blue',
  STORAGE_LOCATION: 'gold',
  PROCESS: 'cyan',
  TABLE: 'green',
  VIEW: 'green',
  MATERIALIZED_VIEW: 'green',
};

/** Accent / border colors shared by list chips and graph nodes. */
export const TYPE_ACCENT: Record<string, string> = {
  DATA_SOURCE: '#722ed1',
  EXTRACTION_SOURCE: '#1677ff',
  STORAGE_LOCATION: '#d48806',
  PROCESS: '#08979c',
  TABLE: '#389e0d',
  VIEW: '#389e0d',
  MATERIALIZED_VIEW: '#237804',
};

/** Soft wash behind PROCESS / actor chips (same in list and graph). */
export const TYPE_WASH: Record<string, string> = {
  PROCESS: 'rgba(8, 151, 156, 0.06)',
};

/** @deprecated use TYPE_ACCENT */
export const TYPE_FILL = TYPE_ACCENT;

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
  /** Outgoing hop label (left→right, or actor→right). Always from flowLabelFor. */
  flowLabel: string;
  /** Incoming hop label when PROCESS is the middle actor (left→actor). */
  inLabel?: string;
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

/** Where an asset was parsed from, using the qualified name already on the lineage node. */
export const originCaption = (qualifiedName?: string): string | null => {
  if (!qualifiedName) {
    return null;
  }
  if (qualifiedName.startsWith('process:airflow:')) {
    const path = qualifiedName.slice('process:airflow:'.length);
    return path ? `Airflow DAG · ${path}` : 'Airflow DAG';
  }
  if (qualifiedName.startsWith('extraction:airflow:')) {
    const id = qualifiedName.slice('extraction:airflow:'.length);
    return id ? `Airflow DAG · ${id}` : 'Airflow DAG';
  }
  if (qualifiedName.startsWith('process:')) {
    const handler = qualifiedName.split(':').pop();
    return handler ? `модуль реестра · ${handler}` : 'модуль реестра';
  }
  if (qualifiedName.startsWith('extraction:')) {
    return 'реестр извлечения';
  }
  return null;
};

export const flowLabelFor = (
  relationshipType: string,
  leftType?: string,
  rightType?: string,
  leftQualifiedName?: string,
  rightQualifiedName?: string
): string => {
  if (
    relationshipType === 'EXTRACTS_TO' &&
    leftType === 'DATA_SOURCE' &&
    rightType === 'EXTRACTION_SOURCE'
  ) {
    return 'предоставляет';
  }
  if (
    relationshipType === 'EXTRACTS_TO' &&
    leftType === 'EXTRACTION_SOURCE' &&
    rightType === 'PROCESS'
  ) {
    return originCaption(rightQualifiedName) ?? originCaption(leftQualifiedName) ?? 'процесс';
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
 * Never leave PROCESS as a dead-end when WRITES_TO edges exist in the payload.
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
    const lefts: Array<LineageNode | null> = sources.length ? sources : [null];
    let emittedWrite = false;
    for (const write of writes) {
      const target = byId.get(write.to_asset_id);
      if (!target) {
        continue;
      }
      emittedWrite = true;
      consumed.add(write.id);
      for (const left of lefts) {
        if (left) {
          rows.push({
            key: `${process.id}:${left.id}:${target.id}:${write.id}`,
            left,
            actor: process,
            right: target,
            inLabel: flowLabelFor(
              'READS_FROM',
              left.asset_type,
              process.asset_type,
              left.qualified_name,
              process.qualified_name
            ),
            flowLabel: flowLabelFor(
              'WRITES_TO',
              process.asset_type,
              target.asset_type,
              process.qualified_name,
              target.qualified_name
            ),
          });
        } else {
          rows.push({
            key: `${process.id}::${target.id}:${write.id}`,
            left: process,
            right: target,
            flowLabel: flowLabelFor(
              'WRITES_TO',
              process.asset_type,
              target.asset_type,
              process.qualified_name,
              target.qualified_name
            ),
          });
        }
      }
    }
    if (emittedWrite) {
      for (const read of reads) {
        consumed.add(read.id);
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
    // Do not show STORAGE→PROCESS alone when this process also writes somewhere
    // in the lineage payload (common when opening lineage from a VIEW).
    if (edge.relationship_type === 'READS_FROM') {
      const process = byId.get(edge.from_asset_id);
      if (
        process?.asset_type === 'PROCESS' &&
        edges.some(
          (item) =>
            item.relationship_type === 'WRITES_TO' &&
            item.from_asset_id === process.id &&
            byId.has(item.to_asset_id)
        )
      ) {
        continue;
      }
    }
    rows.push({
      key: edge.id,
      left: ends.left,
      right: ends.right,
      flowLabel: flowLabelFor(
        edge.relationship_type,
        ends.left.asset_type,
        ends.right.asset_type,
        ends.left.qualified_name,
        ends.right.qualified_name
      ),
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
      label: flowLabelFor(
        edge.relationship_type,
        ends.left.asset_type,
        ends.right.asset_type,
        ends.left.qualified_name,
        ends.right.qualified_name
      ),
      relationshipType: edge.relationship_type,
    });
  }
  return result;
};

export const LINEAGE_NODE_WIDTH = 250;
export const LINEAGE_NODE_HEIGHT = 112;

export type FlowLink = { from: string; to: string };

const pushLink = (map: Map<string, string[]>, key: string, value: string) => {
  const list = map.get(key);
  if (list) {
    list.push(value);
    return;
  }
  map.set(key, [value]);
};

/**
 * Upstream and downstream closure of one asset.
 * Walks only away from the asset, so sibling branches through a shared parent stay out.
 */
export const dependencyIds = (focusId: string, links: FlowLink[]): Set<string> => {
  const downstream = new Map<string, string[]>();
  const upstream = new Map<string, string[]>();
  for (const link of links) {
    pushLink(downstream, link.from, link.to);
    pushLink(upstream, link.to, link.from);
  }
  const result = new Set<string>([focusId]);
  const walk = (next: Map<string, string[]>) => {
    const stack = [focusId];
    const seen = new Set<string>([focusId]);
    while (stack.length) {
      const id = stack.pop();
      if (!id) {
        continue;
      }
      for (const neighbour of next.get(id) ?? []) {
        if (seen.has(neighbour)) {
          continue;
        }
        seen.add(neighbour);
        result.add(neighbour);
        stack.push(neighbour);
      }
    }
  };
  walk(downstream);
  walk(upstream);
  return result;
};

export const linksFromRows = (rows: FlowRow[]): FlowLink[] => {
  const links: FlowLink[] = [];
  for (const row of rows) {
    if (row.actor) {
      links.push({ from: row.left.id, to: row.actor.id });
      links.push({ from: row.actor.id, to: row.right.id });
    } else {
      links.push({ from: row.left.id, to: row.right.id });
    }
  }
  return links;
};

const rowParticipantIds = (row: FlowRow): string[] => {
  const ids = [row.left.id, row.right.id];
  if (row.actor) {
    ids.push(row.actor.id);
  }
  return ids;
};

export const rowInClosure = (row: FlowRow, closure: Set<string>): boolean =>
  rowParticipantIds(row).every((id) => closure.has(id));

/**
 * Keep the clicked row at the same index.
 * Upstream dependency rows sit immediately above it, downstream rows immediately below.
 */
export const focusFlowRows = (
  rows: FlowRow[],
  focusId: string | null,
  anchorKey?: string | null
): { rows: FlowRow[]; anchorKey: string | null; dependencyKeys: Set<string> } => {
  if (!focusId) {
    return { rows, anchorKey: null, dependencyKeys: new Set() };
  }
  const closure = dependencyIds(focusId, linksFromRows(rows));
  const dependencyKeys = new Set(rows.filter((row) => rowInClosure(row, closure)).map((row) => row.key));
  let anchorIndex = anchorKey ? rows.findIndex((row) => row.key === anchorKey) : -1;
  if (anchorIndex < 0) {
    anchorIndex = rows.findIndex((row) => dependencyKeys.has(row.key));
  }
  if (anchorIndex < 0) {
    return { rows, anchorKey: null, dependencyKeys };
  }
  const anchor = rows[anchorIndex];
  const upstream: FlowRow[] = [];
  const downstream: FlowRow[] = [];
  const next: FlowRow[] = [];
  rows.forEach((row, index) => {
    if (index === anchorIndex) {
      next.push(row);
      return;
    }
    if (dependencyKeys.has(row.key) && index < anchorIndex) {
      upstream.push(row);
      return;
    }
    if (dependencyKeys.has(row.key) && index > anchorIndex) {
      downstream.push(row);
      return;
    }
    next.push(row);
  });
  const insertAt = next.findIndex((row) => row.key === anchor.key);
  next.splice(insertAt, 0, ...upstream);
  const anchorAt = insertAt + upstream.length;
  next.splice(anchorAt + 1, 0, ...downstream);
  return { rows: next, anchorKey: anchor.key, dependencyKeys };
};

