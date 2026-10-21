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
export const LINEAGE_NODE_HEIGHT = 96;

const COLUMN_GAP = 88;
const ROW_GAP = 32;

export type LineagePoint = { x: number; y: number };

export type FlowLink = { from: string; to: string; id?: string; label?: string };

export type MapSegment = {
  id: string;
  groupId: string;
  source: string;
  target: string;
  label: string;
  arrow: boolean;
  incident: boolean;
};

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

/** How many hops around the focused asset the map draws. */
export const MAP_HOPS = 4;

const LAYER_GAP = 128;

/**
 * Upstream and downstream assets within `hops` of the focus.
 * Sibling branches beyond that distance stay off the map.
 */
export const neighborhoodIds = (focusId: string, links: FlowLink[], hops = MAP_HOPS): Set<string> => {
  const downstream = new Map<string, string[]>();
  const upstream = new Map<string, string[]>();
  for (const link of links) {
    pushLink(downstream, link.from, link.to);
    pushLink(upstream, link.to, link.from);
  }
  const result = new Set<string>([focusId]);
  const walk = (next: Map<string, string[]>) => {
    let frontier = [focusId];
    const seen = new Set<string>([focusId]);
    for (let hop = 0; hop < hops; hop += 1) {
      const upcoming: string[] = [];
      for (const id of frontier) {
        for (const neighbour of next.get(id) ?? []) {
          if (seen.has(neighbour)) {
            continue;
          }
          seen.add(neighbour);
          result.add(neighbour);
          upcoming.push(neighbour);
        }
      }
      frontier = upcoming;
    }
  };
  walk(downstream);
  walk(upstream);
  return result;
};

const WAYPOINT_SIZE = 8;
const WAYPOINT_GAP = 20;

type RankSlot = { id: string; dummy: boolean };

const reachable = (start: string, next: Map<string, string[]>, allowed: Set<string>): Set<string> => {
  const result = new Set<string>([start]);
  const stack = [start];
  while (stack.length) {
    const id = stack.pop();
    if (!id) {
      continue;
    }
    for (const neighbour of next.get(id) ?? []) {
      if (!allowed.has(neighbour) || result.has(neighbour)) {
        continue;
      }
      result.add(neighbour);
      stack.push(neighbour);
    }
  }
  return result;
};

const longestDistances = (
  start: string,
  next: Map<string, string[]>,
  allowed: Set<string>
): Map<string, number> => {
  const dist = new Map<string, number>([[start, 0]]);
  const ids = [...allowed];
  for (let pass = 0; pass < ids.length; pass += 1) {
    let changed = false;
    for (const id of ids) {
      const base = dist.get(id);
      if (base === undefined) {
        continue;
      }
      for (const neighbour of next.get(id) ?? []) {
        if (!allowed.has(neighbour)) {
          continue;
        }
        const candidate = base + 1;
        if ((dist.get(neighbour) ?? -1) < candidate) {
          dist.set(neighbour, candidate);
          changed = true;
        }
      }
    }
    if (!changed) {
      break;
    }
  }
  return dist;
};

/** Longest path from the focus, so a shortcut cannot pull a node back across another edge. */
const flowRanks = (focusId: string, links: FlowLink[], visible: Set<string>): Map<string, number> => {
  const outgoing = new Map<string, string[]>();
  const incoming = new Map<string, string[]>();
  for (const link of links) {
    if (!visible.has(link.from) || !visible.has(link.to)) {
      continue;
    }
    pushLink(outgoing, link.from, link.to);
    pushLink(incoming, link.to, link.from);
  }
  const downstream = reachable(focusId, outgoing, visible);
  const upstream = reachable(focusId, incoming, visible);
  upstream.delete(focusId);
  const downDist = longestDistances(focusId, outgoing, downstream);
  const upDist = longestDistances(focusId, incoming, upstream);
  const rank = new Map<string, number>();
  for (const [id, distance] of downDist) {
    rank.set(id, distance);
  }
  for (const [id, distance] of upDist) {
    if (!rank.has(id)) {
      rank.set(id, -distance);
    }
  }
  for (const id of visible) {
    if (!rank.has(id)) {
      rank.set(id, 0);
    }
  }
  const ids = [...visible];
  for (let pass = 0; pass < ids.length; pass += 1) {
    let changed = false;
    for (const link of links) {
      if (!visible.has(link.from) || !visible.has(link.to)) {
        continue;
      }
      const from = rank.get(link.from) ?? 0;
      const to = rank.get(link.to) ?? 0;
      if (to <= from) {
        rank.set(link.to, from + 1);
        changed = true;
      }
    }
    if (!changed) {
      break;
    }
  }
  return rank;
};

const expandSegments = (
  links: FlowLink[],
  rank: Map<string, number>,
  focusId: string
): { layers: Map<number, RankSlot[]>; segments: MapSegment[] } => {
  const layers = new Map<number, RankSlot[]>();
  const seen = new Map<number, Set<string>>();
  const add = (layer: number, id: string, dummy: boolean) => {
    const taken = seen.get(layer) ?? new Set<string>();
    if (taken.has(id)) {
      return;
    }
    taken.add(id);
    seen.set(layer, taken);
    const list = layers.get(layer) ?? [];
    list.push({ id, dummy });
    layers.set(layer, list);
  };
  for (const [id, layer] of rank) {
    add(layer, id, false);
  }
  const segments: MapSegment[] = [];
  let dummySeq = 0;
  for (const link of links) {
    const fromRank = rank.get(link.from);
    const toRank = rank.get(link.to);
    if (fromRank === undefined || toRank === undefined || toRank <= fromRank) {
      continue;
    }
    const groupId = link.id ?? `${link.from}->${link.to}`;
    const incident = link.from === focusId || link.to === focusId;
    let previous = link.from;
    for (let layer = fromRank + 1; layer < toRank; layer += 1) {
      const dummyId = `way:${groupId}:${layer}:${dummySeq}`;
      dummySeq += 1;
      add(layer, dummyId, true);
      segments.push({
        id: `${groupId}:${layer}:${dummySeq}`,
        groupId,
        source: previous,
        target: dummyId,
        label: '',
        arrow: false,
        incident,
      });
      previous = dummyId;
    }
    segments.push({
      id: `${groupId}:end`,
      groupId,
      source: previous,
      target: link.to,
      label: link.label ?? '',
      arrow: true,
      incident,
    });
  }
  return { layers, segments };
};

const average = (values: number[], fallback: number) => {
  if (!values.length) {
    return fallback;
  }
  return values.reduce((sum, value) => sum + value, 0) / values.length;
};

const crossingCount = (left: RankSlot[], right: RankSlot[], segments: MapSegment[]): number => {
  const leftPos = new Map(left.map((slot, index) => [slot.id, index]));
  const rightPos = new Map(right.map((slot, index) => [slot.id, index]));
  const pairs: Array<[number, number]> = [];
  for (const segment of segments) {
    const source = leftPos.get(segment.source);
    const target = rightPos.get(segment.target);
    if (source === undefined || target === undefined) {
      continue;
    }
    pairs.push([source, target]);
  }
  let count = 0;
  for (let i = 0; i < pairs.length; i += 1) {
    for (let j = i + 1; j < pairs.length; j += 1) {
      const [leftA, rightA] = pairs[i];
      const [leftB, rightB] = pairs[j];
      if ((leftA - leftB) * (rightA - rightB) < 0) {
        count += 1;
      }
    }
  }
  return count;
};

const orderLayers = (
  layers: Map<number, RankSlot[]>,
  segments: MapSegment[],
  nameOf: (id: string) => string
) => {
  const ranks = [...layers.keys()].sort((a, b) => a - b);
  for (const list of layers.values()) {
    list.sort((a, b) => nameOf(a.id).localeCompare(nameOf(b.id)) || a.id.localeCompare(b.id));
  }
  const neighborPositions = (id: string, other: Map<string, number>) => {
    const values: number[] = [];
    for (const segment of segments) {
      if (segment.source === id) {
        const position = other.get(segment.target);
        if (position !== undefined) {
          values.push(position);
        }
      }
      if (segment.target === id) {
        const position = other.get(segment.source);
        if (position !== undefined) {
          values.push(position);
        }
      }
    }
    return values;
  };
  for (let pass = 0; pass < 8; pass += 1) {
    const sequence = pass % 2 === 0 ? ranks : [...ranks].reverse();
    const direction = pass % 2 === 0 ? 1 : -1;
    for (const rank of sequence) {
      const list = layers.get(rank);
      const other = layers.get(rank + direction);
      if (!list || !other) {
        continue;
      }
      const otherPos = new Map(other.map((slot, index) => [slot.id, index]));
      const current = new Map(list.map((slot, index) => [slot.id, index]));
      list.sort((a, b) => {
        const diff =
          average(neighborPositions(a.id, otherPos), current.get(a.id) ?? 0) -
          average(neighborPositions(b.id, otherPos), current.get(b.id) ?? 0);
        if (diff !== 0) {
          return diff;
        }
        return nameOf(a.id).localeCompare(nameOf(b.id)) || a.id.localeCompare(b.id);
      });
    }
  }
  for (let pass = 0; pass < ranks.length; pass += 1) {
    for (let index = 0; index < ranks.length - 1; index += 1) {
      const left = layers.get(ranks[index]);
      const right = layers.get(ranks[index + 1]);
      if (!left || !right || left.length < 2) {
        continue;
      }
      let improved = true;
      let guard = 0;
      while (improved && guard < left.length * left.length) {
        improved = false;
        guard += 1;
        for (let slot = 0; slot < left.length - 1; slot += 1) {
          const before = crossingCount(left, right, segments);
          const current = left[slot];
          left[slot] = left[slot + 1];
          left[slot + 1] = current;
          if (crossingCount(left, right, segments) < before) {
            improved = true;
            continue;
          }
          const swapped = left[slot];
          left[slot] = left[slot + 1];
          left[slot + 1] = swapped;
        }
      }
    }
  }
};

const placeLayers = (
  layers: Map<number, RankSlot[]>
): { positions: Map<string, LineagePoint>; waypoints: Map<string, LineagePoint> } => {
  const positions = new Map<string, LineagePoint>();
  const waypoints = new Map<string, LineagePoint>();
  const ranks = [...layers.keys()].sort((a, b) => a - b);
  const minRank = ranks[0] ?? 0;
  for (const rank of ranks) {
    const list = layers.get(rank) ?? [];
    let stack = 0;
    list.forEach((slot, index) => {
      if (index > 0) {
        const previous = list[index - 1];
        stack += previous.dummy && slot.dummy ? WAYPOINT_GAP : ROW_GAP;
      }
      stack += slot.dummy ? WAYPOINT_SIZE : LINEAGE_NODE_HEIGHT;
    });
    let y = -stack / 2;
    const x = (rank - minRank) * (LINEAGE_NODE_WIDTH + LAYER_GAP);
    list.forEach((slot, index) => {
      if (index > 0) {
        const previous = list[index - 1];
        y += previous.dummy && slot.dummy ? WAYPOINT_GAP : ROW_GAP;
      }
      if (slot.dummy) {
        waypoints.set(slot.id, { x: x + LINEAGE_NODE_WIDTH / 2 - WAYPOINT_SIZE / 2, y });
        y += WAYPOINT_SIZE;
        return;
      }
      positions.set(slot.id, { x, y });
      y += LINEAGE_NODE_HEIGHT;
    });
  }
  return { positions, waypoints };
};

const placeGrid = (
  nodes: Array<{ id: string; display_name: string }>
): Map<string, LineagePoint> => {
  const ordered = [...nodes].sort(
    (a, b) => a.display_name.localeCompare(b.display_name) || a.id.localeCompare(b.id)
  );
  const columns = Math.max(1, Math.ceil(Math.sqrt(ordered.length)));
  const positions = new Map<string, LineagePoint>();
  ordered.forEach((node, index) => {
    positions.set(node.id, {
      x: (index % columns) * (LINEAGE_NODE_WIDTH + COLUMN_GAP),
      y: Math.floor(index / columns) * (LINEAGE_NODE_HEIGHT + ROW_GAP),
    });
  });
  return positions;
};

export type LineageMapLayout = {
  positions: Map<string, LineagePoint>;
  waypoints: Map<string, LineagePoint>;
  neighborhood: Set<string>;
  /** Unit segments. A long edge is split so it never crosses another column. */
  segments: MapSegment[];
};

/**
 * Left-to-right layers around the focused asset.
 * Each edge steps one column at a time. Nodes in a column are ordered so those
 * steps do not cross.
 */
export const layoutLineageMap = (
  nodes: Array<{ id: string; asset_type: string; display_name: string }>,
  links: FlowLink[],
  focusId: string | null
): LineageMapLayout => {
  const present = new Set(nodes.map((node) => node.id));
  const center = focusId && present.has(focusId) ? focusId : null;
  const neighborhood = center ? neighborhoodIds(center, links) : new Set(nodes.map((node) => node.id));
  const visible = nodes.filter((node) => neighborhood.has(node.id));
  const visibleLinks = links.filter((link) => neighborhood.has(link.from) && neighborhood.has(link.to));
  if (!center || !visibleLinks.length) {
    return { positions: placeGrid(visible), waypoints: new Map(), neighborhood, segments: [] };
  }
  const ranks = flowRanks(center, visibleLinks, neighborhood);
  const nameOf = new Map(nodes.map((node) => [node.id, node.display_name]));
  const { layers, segments } = expandSegments(visibleLinks, ranks, center);
  orderLayers(layers, segments, (id) => nameOf.get(id) ?? id);
  const placed = placeLayers(layers);
  return { positions: placed.positions, waypoints: placed.waypoints, neighborhood, segments };
};
