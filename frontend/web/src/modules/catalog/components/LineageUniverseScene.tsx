import type { LineageEdge, LineageNode } from '@shared/api/generated';
import {
  AimOutlined,
  DragOutlined,
  MinusOutlined,
  PlusOutlined,
  ReloadOutlined,
  RetweetOutlined,
} from '@ant-design/icons';
import { Button, Segmented, Space, Tooltip } from 'antd';
import { useEffect, useRef, useState } from 'react';
import { STAGE_ORDER, TYPE_ACCENT, buildFlowEdges } from './lineageFlow';
import './lineageUniverse.css';

export type UniverseOrigin = { x: number; y: number; z: number };

type Props = {
  nodes: LineageNode[];
  edges: LineageEdge[];
  selectedAssetId?: string;
  /** Roots catalogue: open a source chain. Asset chain: open object card. */
  mode: 'roots' | 'chain';
  /** World point of the clicked ring node — animates chain unfold from here. */
  enterOrigin?: UniverseOrigin | null;
  onSelect?: (assetId: string, origin?: UniverseOrigin) => void;
};

type DragTool = 'orbit' | 'pan';

type SceneControls = {
  zoomIn: () => void;
  zoomOut: () => void;
  resetView: () => void;
  nudge: (dx: number, dy: number) => void;
};

type Body = {
  id: string;
  label: string;
  type: string;
  color: string;
  unresolved?: boolean;
  hubId: string | null;
  shell: number;
  /** VIEW/TABLE fed by 2+ DATA_SOURCE hubs. */
  bridgeHubIds?: string[];
  /** Roots ring: base polar angle / radius for slow spin. */
  ringAngle?: number;
  ringRadius?: number;
  /** Chain enter morph start pose. */
  fromX?: number;
  fromY?: number;
  fromZ?: number;
  x: number;
  y: number;
  z: number;
  vx: number;
  vy: number;
  vz: number;
  r: number;
  homeX: number;
  homeY: number;
  homeZ: number;
};

const EXIT_MS = 720;
const ENTER_MS = 1100;

const clamp01 = (value: number) => Math.max(0, Math.min(1, value));
const easeOutCubic = (t: number) => 1 - (1 - clamp01(t)) ** 3;
const lerp = (a: number, b: number, t: number) => a + (b - a) * t;

type Link = {
  id: string;
  source: string;
  target: string;
  label: string;
};

type Star = { x: number; y: number; z: number; s: number };
type ScreenHit = { id: string; x: number; y: number; r: number; z: number };

const FOCAL = 820;
const DRAG = 0.88;
const HOME_PULL = 0.055;
const CHARGE = 1100;

/** World X columns: DATA_SOURCE → … → TABLE → VIEW → MAT_VIEW (left → right). */
const FLOW_STAGE_X = [-720, -480, -240, 0, 280, 540, 800] as const;
const FLOW_STAGE_LABELS = [
  'SOURCE',
  'EXTRACT',
  'STORAGE',
  'PROCESS',
  'TABLE',
  'VIEW',
  'MAT_VIEW',
] as const;
const NODE_GAP_Z = 78;
const LANE_PAD_Z = 120;
/** Screen chrome + long labels so chain nodes stay inside the canvas. */
const CHAIN_PAD_L = 150;
const CHAIN_PAD_R = 190;
const CHAIN_PAD_T = 96;
const CHAIN_PAD_B = 128;
const LAST_STAGE = FLOW_STAGE_X.length - 1;

const clamp = (value: number, min: number, max: number) =>
  Math.max(min, Math.min(max, value));

const shellForType = (type: string): number => {
  if (type === 'DATA_SOURCE') return 0;
  if (type === 'EXTRACTION_SOURCE') return 1;
  if (type === 'STORAGE_LOCATION') return 2;
  if (type === 'PROCESS') return 3;
  if (type === 'TABLE') return 4;
  if (type === 'VIEW') return 5;
  if (type === 'MATERIALIZED_VIEW') return 6;
  return 4;
};

const seeded = (seed: number) => {
  let s = seed || 1;
  return () => {
    s = (Math.imul(s, 1664525) + 1013904223) >>> 0;
    return s / 4294967296;
  };
};

const nearestHub = (
  startId: string,
  hubs: Set<string>,
  adj: Map<string, string[]>
): string | null => {
  const all = collectHubs(startId, hubs, adj);
  return all[0] ?? null;
};

/** All DATA_SOURCE hubs reachable from a node (for multi-source bridges). */
const collectHubs = (
  startId: string,
  hubs: Set<string>,
  adj: Map<string, string[]>
): string[] => {
  if (hubs.has(startId)) {
    return [startId];
  }
  const found: string[] = [];
  const queue = [startId];
  const seen = new Set([startId]);
  while (queue.length) {
    const id = queue.shift();
    if (!id) {
      continue;
    }
    for (const next of adj.get(id) ?? []) {
      if (seen.has(next)) {
        continue;
      }
      seen.add(next);
      if (hubs.has(next)) {
        found.push(next);
        continue;
      }
      queue.push(next);
    }
  }
  return found.sort();
};

const LineageUniverseScene = ({
  nodes,
  edges,
  selectedAssetId,
  mode,
  enterOrigin = null,
  onSelect,
}: Props) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const overlayRef = useRef<HTMLDivElement>(null);
  const toolRef = useRef<DragTool>('pan');
  const controlsRef = useRef<SceneControls>({
    zoomIn: () => undefined,
    zoomOut: () => undefined,
    resetView: () => undefined,
    nudge: () => undefined,
  });
  const [tool, setTool] = useState<DragTool>('pan');
  toolRef.current = tool;

  useEffect(() => {
    const canvas = canvasRef.current;
    const overlay = overlayRef.current;
    if (!canvas || !overlay) {
      return;
    }
    const ctx = canvas.getContext('2d');
    if (!ctx) {
      return;
    }

    const flow = edges.length ? buildFlowEdges(nodes, edges) : [];
    const links: Link[] = flow.map((edge) => ({
      id: edge.id,
      source: edge.source,
      target: edge.target,
      label: edge.label,
    }));
    const byId = new Map(nodes.map((node) => [node.id, node]));
    const adj = new Map<string, string[]>();
    for (const link of links) {
      const left = adj.get(link.source) ?? [];
      left.push(link.target);
      adj.set(link.source, left);
      const right = adj.get(link.target) ?? [];
      right.push(link.source);
      adj.set(link.target, right);
    }

    const hubs = nodes
      .filter((node) => node.asset_type === 'DATA_SOURCE')
      .sort((a, b) => a.display_name.localeCompare(b.display_name) || a.id.localeCompare(b.id));
    const hubIds = new Set(hubs.map((node) => node.id));
    if (!hubIds.size) {
      for (const node of nodes) {
        if (node.asset_type === 'EXTRACTION_SOURCE') {
          hubIds.add(node.id);
        }
      }
    }
    const hubList = hubs.length
      ? hubs.map((node) => node.id)
      : [...hubIds].sort((a, b) => {
          const left = byId.get(a)?.display_name ?? a;
          const right = byId.get(b)?.display_name ?? b;
          return left.localeCompare(right) || a.localeCompare(b);
        });

    const bridgeOf = new Map<string, string[]>();
    const members = new Map<string, string[]>();
    for (const hub of hubList) {
      members.set(hub, []);
    }
    const orphanIds: string[] = [];
    for (const node of nodes) {
      if (hubIds.has(node.id)) {
        continue;
      }
      const reached = collectHubs(node.id, hubIds, adj);
      if (reached.length >= 2 && shellForType(node.asset_type) >= 4) {
        bridgeOf.set(node.id, reached);
        continue;
      }
      const hub = reached[0] ?? nearestHub(node.id, hubIds, adj);
      if (hub) {
        members.get(hub)?.push(node.id);
      } else {
        orphanIds.push(node.id);
      }
    }

    const hubLane = new Map<string, { z: number; half: number }>();
    const bodies: Body[] = [];
    const placeAt = (
      node: LineageNode,
      shell: number,
      hubId: string | null,
      x: number,
      y: number,
      z: number,
      bridgeHubIds?: string[],
      ring?: { angle: number; radius: number }
    ) => {
      const size =
        shell === 0
          ? 22
          : shell === 1
            ? 16
            : shell >= 4
              ? 14
              : node.asset_type === 'PROCESS'
                ? 15
                : 13;
      bodies.push({
        id: node.id,
        label: node.display_name,
        type: node.asset_type,
        color: node.unresolved
          ? '#ff4d4f'
          : bridgeHubIds?.length
            ? '#fbbf24'
            : TYPE_ACCENT[node.asset_type] || '#8c8c8c',
        unresolved: node.unresolved,
        hubId,
        shell,
        bridgeHubIds,
        ringAngle: ring?.angle,
        ringRadius: ring?.radius,
        x,
        y,
        z,
        homeX: x,
        homeY: y,
        homeZ: z,
        vx: 0,
        vy: 0,
        vz: 0,
        r: node.id === selectedAssetId ? size + 4 : size + (bridgeHubIds?.length ? 3 : 0),
      });
    };

    if (mode === 'roots') {
      // Flat catalogue grid — a spinning ring is unusable past a few dozen hubs.
      const catalogue = [
        ...hubList.map((id) => byId.get(id)).filter((node): node is LineageNode => Boolean(node)),
        ...orphanIds
          .map((id) => byId.get(id))
          .filter((node): node is LineageNode => Boolean(node)),
      ].sort(
        (a, b) =>
          a.display_name.localeCompare(b.display_name) || a.id.localeCompare(b.id)
      );
      const count = Math.max(1, catalogue.length);
      const cols = Math.max(1, Math.ceil(Math.sqrt(count * 1.4)));
      const rows = Math.max(1, Math.ceil(count / cols));
      const gapX = count <= 40 ? 220 : 168;
      const gapZ = count <= 40 ? 120 : 96;
      catalogue.forEach((node, index) => {
        const col = index % cols;
        const row = Math.floor(index / cols);
        const isHub = hubIds.has(node.id);
        placeAt(
          node,
          isHub ? 0 : shellForType(node.asset_type),
          isHub ? node.id : null,
          (col - (cols - 1) / 2) * gapX,
          0,
          (row - (rows - 1) / 2) * gapZ
        );
      });
    } else {
      // Chain: per-hub lanes on Z, stages advance on X (left → right).
      const laneHeights = hubList.map((hub) => {
        const group = members.get(hub) ?? [];
        const counts = new Map<number, number>();
        for (const id of group) {
          const node = byId.get(id);
          if (!node) {
            continue;
          }
          const shell = shellForType(node.asset_type);
          counts.set(shell, (counts.get(shell) ?? 0) + 1);
        }
        const maxStack = Math.max(1, ...counts.values(), 1);
        return Math.max(NODE_GAP_Z + LANE_PAD_Z, (maxStack - 1) * NODE_GAP_Z + LANE_PAD_Z);
      });
      let zCursor = 0;
      hubList.forEach((id, index) => {
        const height = laneHeights[index] ?? LANE_PAD_Z;
        hubLane.set(id, { z: zCursor + height / 2, half: height / 2 });
        zCursor += height;
      });
      const zMid = zCursor / 2;
      for (const lane of hubLane.values()) {
        lane.z -= zMid;
      }

      hubList.forEach((id) => {
        const node = byId.get(id);
        const lane = hubLane.get(id);
        if (!node || !lane) {
          return;
        }
        placeAt(node, 0, id, FLOW_STAGE_X[0], 0, lane.z);
      });

      for (const hub of hubList) {
        const lane = hubLane.get(hub);
        if (!lane) {
          continue;
        }
        const group = (members.get(hub) ?? [])
          .map((id) => byId.get(id))
          .filter((node): node is LineageNode => Boolean(node))
          .sort((a, b) => {
            const shellDiff = shellForType(a.asset_type) - shellForType(b.asset_type);
            if (shellDiff !== 0) {
              return shellDiff;
            }
            return a.display_name.localeCompare(b.display_name);
          });
        const byShell = new Map<number, LineageNode[]>();
        for (const node of group) {
          const shell = shellForType(node.asset_type);
          const list = byShell.get(shell) ?? [];
          list.push(node);
          byShell.set(shell, list);
        }
        for (const [shell, list] of byShell) {
          list.forEach((node, index) => {
            const offset = (index - (list.length - 1) / 2) * NODE_GAP_Z;
            const y = ((index % 3) - 1) * 8;
            placeAt(
              node,
              shell,
              hub,
              FLOW_STAGE_X[shell] ?? FLOW_STAGE_X[LAST_STAGE],
              y,
              lane.z + offset
            );
          });
        }
      }

      if (orphanIds.length) {
        const byShell = new Map<number, string[]>();
        for (const id of orphanIds) {
          const node = byId.get(id);
          if (!node) {
            continue;
          }
          const shell = shellForType(node.asset_type);
          const list = byShell.get(shell) ?? [];
          list.push(id);
          byShell.set(shell, list);
        }
        const orphanBaseZ =
          (hubList.length
            ? Math.max(...[...hubLane.values()].map((lane) => lane.z + lane.half))
            : 0) + LANE_PAD_Z;
        for (const [shell, ids] of byShell) {
          ids.forEach((id, index) => {
            const node = byId.get(id);
            if (!node) {
              return;
            }
            placeAt(
              node,
              shell,
              null,
              FLOW_STAGE_X[shell] ?? FLOW_STAGE_X[LAST_STAGE],
              0,
              orphanBaseZ + index * NODE_GAP_Z
            );
          });
        }
      }

      // Multi-source VIEW/TABLE: own stage column, midway between parent source lanes.
      let bridgeIndex = 0;
      for (const [id, hubs] of bridgeOf) {
        const node = byId.get(id);
        if (!node) {
          continue;
        }
        const shell = shellForType(node.asset_type);
        const zs = hubs
          .map((hub) => hubLane.get(hub)?.z)
          .filter((value): value is number => typeof value === 'number');
        const z =
          zs.length > 0
            ? zs.reduce((sum, value) => sum + value, 0) / zs.length
            : (bridgeIndex - (bridgeOf.size - 1) / 2) * NODE_GAP_Z;
        // Slight X nudge so stacked bridges in the same stage do not overlap.
        const xNudge = ((bridgeIndex % 3) - 1) * 36;
        placeAt(
          node,
          shell,
          null,
          (FLOW_STAGE_X[shell] ?? FLOW_STAGE_X[LAST_STAGE]) + xNudge,
          52,
          z + ((bridgeIndex % 2) * 2 - 1) * 18,
          hubs
        );
        bridgeIndex += 1;
      }
    }

    const fieldBounds = (() => {
      let minX = Infinity;
      let maxX = -Infinity;
      let minY = Infinity;
      let maxY = -Infinity;
      let minZ = Infinity;
      let maxZ = -Infinity;
      for (const body of bodies) {
        minX = Math.min(minX, body.homeX);
        maxX = Math.max(maxX, body.homeX);
        minY = Math.min(minY, body.homeY);
        maxY = Math.max(maxY, body.homeY);
        minZ = Math.min(minZ, body.homeZ);
        maxZ = Math.max(maxZ, body.homeZ);
      }
      if (!Number.isFinite(minX)) {
        return { minX: -200, maxX: 200, minY: -40, maxY: 40, minZ: -160, maxZ: 160 };
      }
      // Pad so labels and outer shells keep margin inside the frame.
      const padX = Math.max(140, (maxX - minX) * 0.12);
      const padZ = Math.max(120, (maxZ - minZ) * 0.12);
      return {
        minX: minX - padX,
        maxX: maxX + padX,
        minY: minY - 40,
        maxY: maxY + 40,
        minZ: minZ - padZ,
        maxZ: maxZ + padZ,
      };
    })();

    const bodyMap = new Map(bodies.map((body) => [body.id, body]));
    const stars: Star[] = Array.from({ length: 180 }, (_, index) => {
      const rnd = seeded(9000 + index * 97);
      return {
        x: (rnd() - 0.5) * 2600,
        y: (rnd() - 0.5) * 1700,
        z: (rnd() - 0.5) * 2600,
        s: 0.4 + rnd() * 1.6,
      };
    });

    let width = 0;
    let height = 0;
    let dpr = 1;
    let yaw = mode === 'roots' ? -0.28 : 0.02;
    let pitch = mode === 'roots' ? 0.52 : 0.82;
    let zoom = 0.85;
    let targetZoom = 0.85;
    let lookX = (fieldBounds.minX + fieldBounds.maxX) / 2;
    let lookY = (fieldBounds.minY + fieldBounds.maxY) / 2;
    let lookZ = (fieldBounds.minZ + fieldBounds.maxZ) / 2;
    let targetLookX = lookX;
    let targetLookY = lookY;
    let targetLookZ = lookZ;
    let panX = 0;
    let panY = 0;
    let dragMode: 'rotate' | 'pan' | null = null;
    let moved = false;
    let lastX = 0;
    let lastY = 0;
    let velYaw = 0;
    let velPitch = 0;
    let hoverId: string | null = null;
    let focusId = selectedAssetId ?? hubList[0] ?? bodies[0]?.id ?? null;
    let pulse = 0;
    let raf = 0;
    let hits: ScreenHit[] = [];
    let userAdjustedView = false;
    let followFocus = false;
    let exitId: string | null = null;
    let exitStarted = 0;
    let exitOrigin: UniverseOrigin | null = null;
    let exitNavigated = false;
    let enterMorph = mode === 'chain' && Boolean(enterOrigin) && !window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    let enterStarted = 0;
    let enterDone = !enterMorph;
    let endLookX = lookX;
    let endLookY = lookY;
    let endLookZ = lookZ;
    let endZoom = zoom;
    let endYaw = yaw;
    let endPitch = pitch;
    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    if (enterMorph && enterOrigin) {
      const hub =
        bodies.find((body) => body.id === selectedAssetId) ??
        bodies.find((body) => body.shell === 0) ??
        null;
      const hx = hub?.homeX ?? enterOrigin.x;
      const hz = hub?.homeZ ?? enterOrigin.z;
      for (const body of bodies) {
        body.fromX = enterOrigin.x + (body.homeX - hx) * 0.04;
        body.fromY = enterOrigin.y + body.homeY * 0.15;
        body.fromZ = enterOrigin.z + (body.homeZ - hz) * 0.04;
        body.x = body.fromX;
        body.y = body.fromY;
        body.z = body.fromZ;
        body.vx = 0;
        body.vy = 0;
        body.vz = 0;
      }
      lookX = targetLookX = enterOrigin.x;
      lookY = targetLookY = enterOrigin.y;
      lookZ = targetLookZ = enterOrigin.z;
      yaw = -0.28;
      pitch = 0.52;
      zoom = targetZoom = 1.45;
    }

    const recomputeFieldBounds = () => {
      let minX = Infinity;
      let maxX = -Infinity;
      let minY = Infinity;
      let maxY = -Infinity;
      let minZ = Infinity;
      let maxZ = -Infinity;
      for (const body of bodies) {
        minX = Math.min(minX, body.homeX);
        maxX = Math.max(maxX, body.homeX);
        minY = Math.min(minY, body.homeY);
        maxY = Math.max(maxY, body.homeY);
        minZ = Math.min(minZ, body.homeZ);
        maxZ = Math.max(maxZ, body.homeZ);
      }
      if (!Number.isFinite(minX)) {
        return;
      }
      const padX = Math.max(120, (maxX - minX) * 0.08);
      const padZ = Math.max(100, (maxZ - minZ) * 0.1);
      fieldBounds.minX = minX - padX;
      fieldBounds.maxX = maxX + padX;
      fieldBounds.minY = minY - 40;
      fieldBounds.maxY = maxY + 40;
      fieldBounds.minZ = minZ - padZ;
      fieldBounds.maxZ = maxZ + padZ;
    };

    const fitScene = (snap = false) => {
      if (!width || !height || !bodies.length) {
        return;
      }
      followFocus = false;
      velYaw = 0;
      velPitch = 0;
      panX = 0;
      panY = 0;

      if (mode === 'roots') {
        // Slight tilt over a flat XZ grid — readable rows, not an edge-on ring.
        yaw = 0;
        pitch = 0.72;
        recomputeFieldBounds();
        const cx = (fieldBounds.minX + fieldBounds.maxX) / 2;
        const cy = (fieldBounds.minY + fieldBounds.maxY) / 2;
        const cz = (fieldBounds.minZ + fieldBounds.maxZ) / 2;
        const spanX = Math.max(280, fieldBounds.maxX - fieldBounds.minX);
        const spanZ = Math.max(220, fieldBounds.maxZ - fieldBounds.minZ);
        const span = Math.max(spanX, spanZ * 1.05);
        targetZoom = clamp((Math.min(width, height) * 0.86) / span, 0.18, 2.4);
        targetLookX = cx;
        targetLookY = cy;
        targetLookZ = cz;
      endLookX = targetLookX;
      endLookY = targetLookY;
      endLookZ = targetLookZ;
      endZoom = targetZoom;
      endYaw = yaw;
      endPitch = pitch;
      if (snap) {
        lookX = cx;
        lookY = cy;
        lookZ = cz;
        zoom = targetZoom;
      }
      return;
    }

      // Chain: contain in viewport (labels need side margins). Left-biased, never clip right.
      yaw = 0;
      pitch = 0.7;
      const minX = Math.min(...bodies.map((body) => body.homeX));
      const maxX = Math.max(...bodies.map((body) => body.homeX));
      const minZ = Math.min(...bodies.map((body) => body.homeZ));
      const maxZ = Math.max(...bodies.map((body) => body.homeZ));
      const minY = Math.min(...bodies.map((body) => body.homeY));
      const maxY = Math.max(...bodies.map((body) => body.homeY));
      let spanX = Math.max(280, maxX - minX);
      const spanZ = Math.max(180, maxZ - minZ);
      const spanY = Math.max(40, maxY - minY);

      const usableW = Math.max(260, width - CHAIN_PAD_L - CHAIN_PAD_R);
      const usableH = Math.max(200, height - CHAIN_PAD_T - CHAIN_PAD_B);
      // Extra world pad ≈ half a long label at typical zoom.
      const labelPad = Math.max(150, spanX * 0.08);
      let spanXPad = spanX + labelPad * 2;
      const spanZPad = spanZ + 90 + spanY * 0.25;

      let nextZoom = clamp(
        Math.min(usableW / spanXPad, usableH / (spanZPad * 0.92)),
        0.34,
        2.1
      );

      // If height leaves unused width, gently widen stages — but keep a safety margin.
      const widthRoom = usableW / (spanXPad * nextZoom);
      if (widthRoom > 1.04 && widthRoom < 1.35) {
        const scale = Math.min(1.18, widthRoom * 0.92);
        for (const body of bodies) {
          const nextX = minX + (body.homeX - minX) * scale;
          body.homeX = nextX;
          body.x = nextX;
        }
        spanX *= scale;
        spanXPad = spanX + labelPad * 2;
        nextZoom = clamp(
          Math.min(usableW / spanXPad, usableH / (spanZPad * 0.92)),
          0.34,
          2.1
        );
      }

      // If still wider than the screen, compress X to fit.
      if (spanXPad * nextZoom > usableW) {
        const shrink = usableW / (spanXPad * nextZoom);
        for (const body of bodies) {
          const nextX = minX + (body.homeX - minX) * shrink;
          body.homeX = nextX;
          body.x = nextX;
        }
        spanX *= shrink;
        spanXPad = spanX + labelPad * 2;
        nextZoom = clamp(
          Math.min(usableW / spanXPad, usableH / (spanZPad * 0.92)),
          0.34,
          2.1
        );
      }

      recomputeFieldBounds();
      const contentMinX = Math.min(...bodies.map((body) => body.homeX));
      const contentMaxX = Math.max(...bodies.map((body) => body.homeX));
      const cy = (minY + maxY) / 2;
      const cz = (minZ + maxZ) / 2;
      // Left edge of content (+ label pad) at CHAIN_PAD_L.
      let lookAtX = contentMinX - labelPad + (width / 2 - CHAIN_PAD_L) / nextZoom;
      // Guarantee right edge also stays inside after perspective slack.
      const rightWorld = contentMaxX + labelPad;
      const rightScreen = width / 2 + (rightWorld - lookAtX) * nextZoom;
      if (rightScreen > width - CHAIN_PAD_R) {
        const overflow = rightScreen - (width - CHAIN_PAD_R);
        nextZoom = clamp(nextZoom * (1 - overflow / Math.max(width, 1)), 0.32, nextZoom);
        lookAtX = contentMinX - labelPad + (width / 2 - CHAIN_PAD_L) / nextZoom;
        const rightScreen2 = width / 2 + (rightWorld - lookAtX) * nextZoom;
        if (rightScreen2 > width - CHAIN_PAD_R) {
          lookAtX += (rightScreen2 - (width - CHAIN_PAD_R)) / nextZoom;
        }
      }

      targetZoom = nextZoom;
      targetLookX = lookAtX;
      targetLookY = cy;
      targetLookZ = cz;
      endLookX = lookAtX;
      endLookY = cy;
      endLookZ = cz;
      endZoom = nextZoom;
      endYaw = yaw;
      endPitch = pitch;
      if (snap && !enterMorph) {
        lookX = lookAtX;
        lookY = cy;
        lookZ = cz;
        zoom = nextZoom;
      }
    };

    const flyToBody = (id: string | null) => {
      if (!id) {
        return;
      }
      const body = bodyMap.get(id);
      if (!body) {
        return;
      }
      focusId = id;
      followFocus = true;
      userAdjustedView = true;
      targetLookX = body.x;
      targetLookY = body.y;
      targetLookZ = body.z;
      panX *= 0.35;
      panY *= 0.35;
    };

    const project = (x: number, y: number, z: number) => {
      const lx = x - lookX;
      const ly = y - lookY;
      const lz = z - lookZ;
      const cy = Math.cos(yaw);
      const sy = Math.sin(yaw);
      const cp = Math.cos(pitch);
      const sp = Math.sin(pitch);
      const x1 = lx * cy - lz * sy;
      const z1 = lx * sy + lz * cy;
      const y1 = ly * cp - z1 * sp;
      const z2 = ly * sp + z1 * cp;
      const depth = FOCAL / (FOCAL + z2 * zoom);
      return {
        x: width / 2 + panX + x1 * depth * zoom,
        y: height / 2 + panY + y1 * depth * zoom * 0.92,
        depth,
        z: z2,
      };
    };

    const resize = () => {
      const parent = canvas.parentElement;
      if (!parent) {
        return;
      }
      width = parent.clientWidth;
      height = parent.clientHeight;
      dpr = Math.min(window.devicePixelRatio || 1, 2);
      canvas.width = Math.max(1, Math.floor(width * dpr));
      canvas.height = Math.max(1, Math.floor(height * dpr));
      canvas.style.width = `${width}px`;
      canvas.style.height = `${height}px`;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      if (!userAdjustedView) {
        if (enterMorph && !enterDone) {
          fitScene(false);
        } else {
          fitScene(true);
        }
      }
    };

    const stepPhysics = () => {
      for (let i = 0; i < bodies.length; i += 1) {
        const a = bodies[i];
        a.vx += (a.homeX - a.x) * HOME_PULL;
        a.vy += (a.homeY - a.y) * HOME_PULL;
        a.vz += (a.homeZ - a.z) * HOME_PULL;
        for (let j = i + 1; j < bodies.length; j += 1) {
          const b = bodies[j];
          let dx = a.x - b.x;
          let dy = a.y - b.y;
          let dz = a.z - b.z;
          const dist2 = dx * dx + dy * dy + dz * dz + 80;
          const force = CHARGE / dist2;
          const dist = Math.sqrt(dist2);
          dx = (dx / dist) * force;
          dy = (dy / dist) * force;
          dz = (dz / dist) * force;
          a.vx += dx;
          a.vy += dy;
          a.vz += dz;
          b.vx -= dx;
          b.vy -= dy;
          b.vz -= dz;
        }
      }
      for (const body of bodies) {
        body.vx *= DRAG;
        body.vy *= DRAG;
        body.vz *= DRAG;
        body.x += body.vx;
        body.y += body.vy;
        body.z += body.vz;
      }
    };

    const hitTest = (mx: number, my: number): string | null => {
      let best: ScreenHit | null = null;
      for (const hit of hits) {
        const dx = mx - hit.x;
        const dy = my - hit.y;
        if (dx * dx + dy * dy <= hit.r * hit.r) {
          if (!best || hit.z < best.z) {
            best = hit;
          }
        }
      }
      return best?.id ?? null;
    };

    const drawArrow = (x1: number, y1: number, x2: number, y2: number, color: string) => {
      const angle = Math.atan2(y2 - y1, x2 - x1);
      const size = 9;
      ctx.fillStyle = color;
      ctx.beginPath();
      ctx.moveTo(x2, y2);
      ctx.lineTo(x2 - size * Math.cos(angle - 0.4), y2 - size * Math.sin(angle - 0.4));
      ctx.lineTo(x2 - size * Math.cos(angle + 0.4), y2 - size * Math.sin(angle + 0.4));
      ctx.closePath();
      ctx.fill();
    };

    const drawLabel = (text: string, x: number, y: number, emphasis: boolean) => {
      ctx.font = `${emphasis ? 600 : 500} ${emphasis ? 13 : 12}px "Segoe UI", system-ui, sans-serif`;
      const widthText = ctx.measureText(text).width;
      const padX = 8;
      const boxW = widthText + padX * 2;
      const boxH = 22;
      const left = x - boxW / 2;
      const top = y;
      // Keep labels readable but translucent so edges stay visible underneath.
      ctx.fillStyle = emphasis ? 'rgba(15, 23, 42, 0.42)' : 'rgba(8, 12, 24, 0.22)';
      ctx.strokeStyle = emphasis ? 'rgba(125, 211, 252, 0.35)' : 'rgba(255,255,255,0.08)';
      ctx.lineWidth = 1;
      if (typeof ctx.roundRect === 'function') {
        ctx.beginPath();
        ctx.roundRect(left, top, boxW, boxH, 8);
      } else {
        ctx.beginPath();
        ctx.rect(left, top, boxW, boxH);
      }
      ctx.fill();
      ctx.stroke();
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.lineWidth = 3;
      ctx.strokeStyle = 'rgba(5, 7, 15, 0.55)';
      ctx.strokeText(text, x, top + boxH / 2);
      ctx.fillStyle = emphasis ? '#f8fbff' : 'rgba(248, 251, 255, 0.88)';
      ctx.fillText(text, x, top + boxH / 2);
    };

    const drawFrame = () => {
      const now = performance.now();
      pulse += reduced ? 0 : 0.03;

      // Roots → chain exit: zoom into the chosen source, fade the rest, then navigate.
      let exitT = 0;
      if (exitId) {
        exitT = easeOutCubic((now - exitStarted) / EXIT_MS);
        const selected = bodyMap.get(exitId);
        if (selected) {
          targetLookX = selected.x;
          targetLookY = selected.y;
          targetLookZ = selected.z;
          targetZoom = lerp(targetZoom, 1.55, 0.08);
          yaw = lerp(yaw, -0.22, 0.06);
          pitch = lerp(pitch, 0.5, 0.06);
        }
        if (exitT >= 1 && !exitNavigated) {
          exitNavigated = true;
          onSelect?.(exitId, exitOrigin ?? undefined);
        }
      }

      // Chain enter: unfold from ring point into LTR layout.
      let enterT = 1;
      if (enterMorph && !enterDone && enterOrigin) {
        if (!enterStarted) {
          enterStarted = now;
        }
        enterT = easeOutCubic((now - enterStarted) / ENTER_MS);
        for (const body of bodies) {
          const fromX = body.fromX ?? body.homeX;
          const fromY = body.fromY ?? body.homeY;
          const fromZ = body.fromZ ?? body.homeZ;
          body.x = lerp(fromX, body.homeX, enterT);
          body.y = lerp(fromY, body.homeY, enterT);
          body.z = lerp(fromZ, body.homeZ, enterT);
          body.vx = 0;
          body.vy = 0;
          body.vz = 0;
        }
        lookX = lerp(enterOrigin.x, endLookX, enterT);
        lookY = lerp(enterOrigin.y, endLookY, enterT);
        lookZ = lerp(enterOrigin.z, endLookZ, enterT);
        yaw = lerp(-0.28, endYaw, enterT);
        pitch = lerp(0.52, endPitch, enterT);
        zoom = lerp(1.45, endZoom, enterT);
        targetLookX = lookX;
        targetLookY = lookY;
        targetLookZ = lookZ;
        targetZoom = zoom;
        if (enterT >= 1) {
          enterDone = true;
          enterMorph = false;
          fitScene(true);
        }
      } else {
        zoom += (targetZoom - zoom) * 0.08;
        const lookEase = reduced ? 1 : 0.08;
        lookX += (targetLookX - lookX) * lookEase;
        lookY += (targetLookY - lookY) * lookEase;
        lookZ += (targetLookZ - lookZ) * lookEase;
      }

      // Soft-follow only after an explicit fly-to (not the default overview).
      if (followFocus && focusId && !enterMorph && !exitId) {
        const focused = bodyMap.get(focusId);
        if (focused) {
          targetLookX += (focused.x - targetLookX) * 0.12;
          targetLookY += (focused.y - targetLookY) * 0.12;
          targetLookZ += (focused.z - targetLookZ) * 0.12;
        }
      }

      // Catalogue grid stays still; orbit inertia only in chain view.
      if (!dragMode && !reduced && !hoverId && mode === 'chain' && enterDone) {
        yaw += velYaw;
        pitch += velPitch;
        velYaw *= 0.96;
        velPitch *= 0.96;
        if (Math.abs(velYaw) < 0.00002) {
          velYaw = 0;
        }
        if (Math.abs(velPitch) < 0.00002) {
          velPitch = 0;
        }
      }

      if (!reduced && enterDone && !exitId) {
        stepPhysics();
      }

      const sky = ctx.createRadialGradient(
        width * 0.5,
        height * 0.4,
        20,
        width * 0.5,
        height * 0.5,
        Math.max(width, height) * 0.8
      );
      sky.addColorStop(0, '#1a2744');
      sky.addColorStop(0.45, '#0b1224');
      sky.addColorStop(1, '#05070f');
      ctx.fillStyle = sky;
      ctx.fillRect(0, 0, width, height);

      const nebula = ctx.createRadialGradient(width * 0.18, height * 0.22, 10, width * 0.18, height * 0.22, width * 0.42);
      nebula.addColorStop(0, 'rgba(88, 28, 135, 0.2)');
      nebula.addColorStop(1, 'rgba(88, 28, 135, 0)');
      ctx.fillStyle = nebula;
      ctx.fillRect(0, 0, width, height);

      for (const star of stars) {
        const p = project(star.x, star.y, star.z);
        if (p.depth <= 0.02) {
          continue;
        }
        ctx.fillStyle = `rgba(255,255,255,${Math.min(1, 0.2 + p.depth * 0.75)})`;
        ctx.beginPath();
        ctx.arc(p.x, p.y, star.s * p.depth, 0, Math.PI * 2);
        ctx.fill();
      }

      ctx.save();
      if (mode === 'roots') {
        const ringR =
          bodies.reduce((sum, body) => sum + Math.hypot(body.homeX, body.homeZ), 0) /
            Math.max(1, bodies.length) || 420;
        const samples = 72;
        ctx.beginPath();
        for (let i = 0; i <= samples; i += 1) {
          const angle = (i / samples) * Math.PI * 2;
          const p = project(Math.cos(angle) * ringR, 0, Math.sin(angle) * ringR);
          if (i === 0) {
            ctx.moveTo(p.x, p.y);
          } else {
            ctx.lineTo(p.x, p.y);
          }
        }
        ctx.strokeStyle = 'rgba(125, 211, 252, 0.22)';
        ctx.lineWidth = 1.2;
        ctx.setLineDash([6, 12]);
        ctx.stroke();
        const caption = project(0, 0, -ringR - 48);
        ctx.setLineDash([]);
        ctx.font = '12px "Segoe UI", system-ui, sans-serif';
        ctx.fillStyle = 'rgba(186, 210, 255, 0.72)';
        ctx.textAlign = 'center';
        ctx.fillText('Каталог источников · клик — открыть поток', caption.x, caption.y);
      } else {
        const zTop = fieldBounds.minZ;
        const zBottom = fieldBounds.maxZ;
        const stageXs = FLOW_STAGE_X.map((fallback, shell) => {
          const xs = bodies.filter((body) => body.shell === shell).map((body) => body.homeX);
          if (!xs.length) {
            return fallback;
          }
          return xs.reduce((sum, value) => sum + value, 0) / xs.length;
        });
        stageXs.forEach((stageX, index) => {
          const a = project(stageX, 0, zTop);
          const b = project(stageX, 0, zBottom);
          ctx.beginPath();
          ctx.moveTo(a.x, a.y);
          ctx.lineTo(b.x, b.y);
          ctx.strokeStyle =
            index === 0 ? 'rgba(125, 211, 252, 0.28)' : 'rgba(148, 163, 184, 0.14)';
          ctx.lineWidth = index === 0 || index === stageXs.length - 1 ? 1.4 : 1;
          ctx.setLineDash(index === 0 ? [] : [5, 10]);
          ctx.stroke();
          const labelAt = project(stageX, 0, zTop - 36);
          ctx.font = '11px "Segoe UI", system-ui, sans-serif';
          ctx.fillStyle = 'rgba(186, 210, 255, 0.7)';
          ctx.textAlign = 'center';
          ctx.fillText(FLOW_STAGE_LABELS[index] ?? '', labelAt.x, labelAt.y);
        });
        const midZ = (fieldBounds.minZ + fieldBounds.maxZ) / 2;
        const flowFrom = project(stageXs[0] ?? FLOW_STAGE_X[0], 0, midZ);
        const flowTo = project(stageXs[LAST_STAGE] ?? FLOW_STAGE_X[LAST_STAGE], 0, midZ);
        ctx.setLineDash([]);
        ctx.strokeStyle = 'rgba(125, 211, 252, 0.22)';
        ctx.lineWidth = 1.2;
        ctx.beginPath();
        ctx.moveTo(flowFrom.x, flowFrom.y);
        ctx.lineTo(flowTo.x, flowTo.y);
        ctx.stroke();
        drawArrow(flowFrom.x, flowFrom.y, flowTo.x, flowTo.y, 'rgba(125, 211, 252, 0.55)');
        for (const lane of hubLane.values()) {
          const left = project(fieldBounds.minX, 0, lane.z - lane.half + 8);
          const right = project(fieldBounds.maxX, 0, lane.z - lane.half + 8);
          ctx.beginPath();
          ctx.moveTo(left.x, left.y);
          ctx.lineTo(right.x, right.y);
          ctx.strokeStyle = 'rgba(134, 239, 172, 0.1)';
          ctx.setLineDash([3, 12]);
          ctx.stroke();
        }
      }
      ctx.restore();
      ctx.setLineDash([]);

      const projectedLinks = links
        .map((link) => {
          const a = bodyMap.get(link.source);
          const b = bodyMap.get(link.target);
          if (!a || !b) {
            return null;
          }
          return {
            link,
            a,
            b,
            pa: project(a.x, a.y, a.z),
            pb: project(b.x, b.y, b.z),
          };
        })
        .filter((item): item is NonNullable<typeof item> => Boolean(item))
        .sort((left, right) => (left.pa.z + left.pb.z) / 2 - (right.pa.z + right.pb.z) / 2);

      for (const item of projectedLinks) {
        const hot =
          item.a.id === focusId ||
          item.b.id === focusId ||
          item.a.id === hoverId ||
          item.b.id === hoverId;
        const midX = (item.pa.x + item.pb.x) / 2;
        const midY = (item.pa.y + item.pb.y) / 2 - (hot ? 34 : 22);
        const grad = ctx.createLinearGradient(item.pa.x, item.pa.y, item.pb.x, item.pb.y);
        grad.addColorStop(0, item.a.color);
        grad.addColorStop(1, item.b.color);
        const exitFade =
          exitId && item.a.id !== exitId && item.b.id !== exitId ? 1 - exitT * 0.9 : 1;
        ctx.globalAlpha = (hot ? 0.95 : 0.55) * exitFade;
        ctx.strokeStyle = grad;
        ctx.lineWidth = hot ? 3 : 1.8;
        ctx.beginPath();
        ctx.moveTo(item.pa.x, item.pa.y);
        ctx.quadraticCurveTo(midX, midY, item.pb.x, item.pb.y);
        ctx.stroke();
        drawArrow(midX, midY, item.pb.x, item.pb.y, hot ? '#ffffff' : item.b.color);
        if (hot) {
          ctx.setLineDash([8, 14]);
          ctx.lineDashOffset = -pulse * 16;
          ctx.strokeStyle = 'rgba(255,255,255,0.7)';
          ctx.lineWidth = 1.2;
          ctx.beginPath();
          ctx.moveTo(item.pa.x, item.pa.y);
          ctx.quadraticCurveTo(midX, midY, item.pb.x, item.pb.y);
          ctx.stroke();
          ctx.setLineDash([]);
          ctx.font = '11px "Segoe UI", system-ui, sans-serif';
          ctx.fillStyle = 'rgba(255,255,255,0.9)';
          ctx.textAlign = 'center';
          ctx.fillText(item.link.label, midX, midY - 8);
        }
        ctx.globalAlpha = 1;
      }

      // Bridge cues: dashed spokes from multi-source VIEW/TABLE to each DATA_SOURCE.
      if (mode === 'chain') {
        for (const body of bodies) {
          if (!body.bridgeHubIds?.length) {
            continue;
          }
          const pb = project(body.x, body.y, body.z);
          for (const hubId of body.bridgeHubIds) {
            const hub = bodyMap.get(hubId);
            if (!hub) {
              continue;
            }
            const ph = project(hub.x, hub.y, hub.z);
            ctx.setLineDash([5, 8]);
            ctx.strokeStyle = 'rgba(251, 191, 36, 0.55)';
            ctx.lineWidth = 1.4;
            ctx.beginPath();
            ctx.moveTo(ph.x, ph.y);
            ctx.lineTo(pb.x, pb.y);
            ctx.stroke();
          }
          ctx.setLineDash([]);
        }
      }

      hits = [];
      const projectedBodies = bodies
        .map((body) => ({ body, p: project(body.x, body.y, body.z) }))
        .sort((left, right) => right.p.z - left.p.z);

      for (const { body, p } of projectedBodies) {
        if (p.depth <= 0.04) {
          continue;
        }
        const active = body.id === focusId || body.id === hoverId || body.id === selectedAssetId;
        const radius = Math.max(10, body.r * p.depth * (active ? 1.35 : 1.15));
        const hitR = Math.max(28, radius + 18);
        hits.push({ id: body.id, x: p.x, y: p.y, r: hitR, z: p.z });
        const exitFade = exitId && body.id !== exitId ? 1 - exitT * 0.92 : 1;
        ctx.globalAlpha = exitFade;

        const glow = ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, radius * 2.8);
        glow.addColorStop(0, `${body.color}bb`);
        glow.addColorStop(0.4, `${body.color}44`);
        glow.addColorStop(1, `${body.color}00`);
        ctx.fillStyle = glow;
        ctx.beginPath();
        ctx.arc(p.x, p.y, radius * 2.8, 0, Math.PI * 2);
        ctx.fill();

        const core = ctx.createRadialGradient(
          p.x - radius * 0.28,
          p.y - radius * 0.28,
          radius * 0.12,
          p.x,
          p.y,
          radius
        );
        core.addColorStop(0, '#ffffff');
        core.addColorStop(0.28, body.color);
        core.addColorStop(1, '#0b1224');
        ctx.fillStyle = core;
        ctx.beginPath();
        ctx.arc(p.x, p.y, radius, 0, Math.PI * 2);
        ctx.fill();
        ctx.strokeStyle = active ? 'rgba(255,255,255,0.85)' : 'rgba(255,255,255,0.25)';
        ctx.lineWidth = active ? 2 : 1;
        ctx.stroke();

        if (body.shell === 0) {
          ctx.strokeStyle = `rgba(125, 211, 252,${0.35 + Math.sin(pulse * 2) * 0.15})`;
          ctx.lineWidth = 1.4;
          ctx.beginPath();
          ctx.arc(p.x, p.y, radius + 8, 0, Math.PI * 2);
          ctx.stroke();
        }
        if (body.bridgeHubIds?.length) {
          ctx.strokeStyle = `rgba(251, 191, 36,${0.45 + Math.sin(pulse * 2) * 0.2})`;
          ctx.lineWidth = 1.6;
          ctx.setLineDash([4, 5]);
          ctx.beginPath();
          ctx.arc(p.x, p.y, radius + 10, 0, Math.PI * 2);
          ctx.stroke();
          ctx.setLineDash([]);
        }

        // Dense catalogues: labels only for focus/hover, or when zoomed in enough.
        const showLabel =
          active ||
          bodies.length <= 48 ||
          zoom >= 0.75 ||
          (mode === 'roots' && bodies.length <= 72 && zoom >= 0.45);
        if (showLabel) {
          drawLabel(body.label, p.x, p.y + radius + 10, active);
          ctx.font = '10px "Segoe UI", system-ui, sans-serif';
          ctx.fillStyle = active ? 'rgba(186, 210, 255, 0.95)' : 'rgba(186, 210, 255, 0.65)';
          ctx.textAlign = 'center';
          ctx.textBaseline = 'top';
          const typeLine = body.bridgeHubIds?.length
            ? `${body.type} · bridge×${body.bridgeHubIds.length}`
            : body.type;
          ctx.fillText(typeLine, p.x, p.y + radius + 36);
          if (active) {
            ctx.fillStyle = 'rgba(255,255,255,0.78)';
            ctx.fillText(
              mode === 'roots'
                ? 'клик — цепочка · двойной — сюда'
                : 'клик — карточка · двойной — сюда',
              p.x,
              p.y + radius + 50
            );
          }
        }
        ctx.globalAlpha = 1;
      }

      // legend + controls
      const legendX = 20;
      let legendY = height - 22 - STAGE_ORDER.length * 18;
      ctx.font = '11px "Segoe UI", system-ui, sans-serif';
      ctx.fillStyle = 'rgba(255,255,255,0.55)';
      ctx.textAlign = 'left';
      ctx.fillText(links.length ? `Связей: ${links.length}` : 'Связей в этом виде нет — это каталог корней', legendX, legendY - 18);
      for (const type of STAGE_ORDER) {
        if (!nodes.some((node) => node.asset_type === type)) {
          continue;
        }
        const color = TYPE_ACCENT[type] || '#8c8c8c';
        ctx.fillStyle = color;
        ctx.beginPath();
        ctx.arc(legendX + 6, legendY, 5, 0, Math.PI * 2);
        ctx.fill();
        ctx.fillStyle = 'rgba(226, 232, 240, 0.85)';
        ctx.fillText(type, legendX + 18, legendY + 4);
        legendY += 18;
      }

      const tipId = hoverId ?? focusId;
      const tip = tipId ? byId.get(tipId) : null;
      const tipBody = tipId ? bodyMap.get(tipId) : null;
      if (tip) {
        overlay.dataset.visible = '1';
        const bridgeNames = (tipBody?.bridgeHubIds ?? [])
          .map((id) => byId.get(id)?.display_name || id)
          .join(' · ');
        const action =
          mode === 'roots'
            ? 'Кликните, чтобы раскрыть поток источника слева направо'
            : tipBody?.bridgeHubIds?.length
              ? `Мост между источниками: ${bridgeNames}`
              : 'Кликните, чтобы открыть карточку объекта';
        overlay.innerHTML = `<strong>${tip.display_name}</strong><span>${tip.asset_type}${
          tipBody?.bridgeHubIds?.length ? ' · BRIDGE' : ''
        }</span><em>${tip.qualified_name || tip.id}</em><small>${action}</small>`;
      } else {
        overlay.dataset.visible = '0';
      }

      raf = requestAnimationFrame(drawFrame);
    };

    const resetView = () => {
      focusId = selectedAssetId ?? hubList[0] ?? bodies[0]?.id ?? null;
      userAdjustedView = false;
      fitScene(true);
    };

    controlsRef.current = {
      zoomIn: () => {
        targetZoom = Math.min(2.4, targetZoom * 1.14);
      },
      zoomOut: () => {
        targetZoom = Math.max(0.45, targetZoom / 1.14);
      },
      resetView,
      nudge: (dx, dy) => {
        userAdjustedView = true;
        panX += dx;
        panY += dy;
      },
    };

    const onPointerDown = (event: PointerEvent) => {
      moved = false;
      lastX = event.clientX;
      lastY = event.clientY;
      velYaw = 0;
      velPitch = 0;
      const forceOrbit = event.shiftKey || event.altKey;
      const forcePan = event.button === 1 || event.button === 2;
      if (forcePan) {
        dragMode = 'pan';
      } else if (forceOrbit) {
        dragMode = 'rotate';
      } else {
        dragMode = toolRef.current === 'pan' ? 'pan' : 'rotate';
      }
      canvas.setPointerCapture(event.pointerId);
    };
    const onPointerMove = (event: PointerEvent) => {
      const rect = canvas.getBoundingClientRect();
      hoverId = hitTest(event.clientX - rect.left, event.clientY - rect.top);
      const idleCursor = toolRef.current === 'pan' ? 'move' : 'grab';
      canvas.style.cursor = hoverId
        ? 'pointer'
        : dragMode === 'pan'
          ? 'move'
          : dragMode
            ? 'grabbing'
            : idleCursor;
      if (!dragMode) {
        return;
      }
      const dx = event.clientX - lastX;
      const dy = event.clientY - lastY;
      if (Math.abs(dx) + Math.abs(dy) > 3) {
        moved = true;
      }
      lastX = event.clientX;
      lastY = event.clientY;
      userAdjustedView = true;
      if (dragMode === 'pan') {
        panX += dx;
        panY += dy;
        return;
      }
      yaw += dx * 0.004;
      pitch = Math.max(-1.05, Math.min(1.15, pitch + dy * 0.0035));
      velYaw = Math.max(-0.00035, Math.min(0.00035, dx * 0.00008));
      velPitch = Math.max(-0.0002, Math.min(0.0002, dy * 0.00005));
    };
    const onPointerUp = (event: PointerEvent) => {
      dragMode = null;
      try {
        canvas.releasePointerCapture(event.pointerId);
      } catch {
        // ignore
      }
    };
    const onContextMenu = (event: MouseEvent) => {
      event.preventDefault();
    };
    const onClick = (event: MouseEvent) => {
      if (moved || exitId) {
        return;
      }
      const rect = canvas.getBoundingClientRect();
      const id = hitTest(event.clientX - rect.left, event.clientY - rect.top);
      if (!id) {
        return;
      }
      focusId = id;
      if (mode === 'roots') {
        const body = bodyMap.get(id);
        if (!body) {
          return;
        }
        exitId = id;
        exitStarted = performance.now();
        exitOrigin = { x: body.x, y: body.y, z: body.z };
        followFocus = true;
        return;
      }
      onSelect?.(id);
    };
    const onDblClick = (event: MouseEvent) => {
      event.preventDefault();
      const rect = canvas.getBoundingClientRect();
      const id = hitTest(event.clientX - rect.left, event.clientY - rect.top);
      if (id) {
        flyToBody(id);
        return;
      }
      resetView();
    };
    const onWheel = (event: WheelEvent) => {
      event.preventDefault();
      userAdjustedView = true;
      targetZoom = Math.max(0.45, Math.min(2.4, targetZoom * (event.deltaY > 0 ? 0.92 : 1.08)));
    };
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Home' || event.key === '0') {
        resetView();
        return;
      }
      if (event.key === '+' || event.key === '=') {
        controlsRef.current.zoomIn();
        return;
      }
      if (event.key === '-' || event.key === '_') {
        controlsRef.current.zoomOut();
        return;
      }
      const step = event.shiftKey ? 48 : 28;
      if (event.key === 'ArrowLeft') {
        panX += step;
      } else if (event.key === 'ArrowRight') {
        panX -= step;
      } else if (event.key === 'ArrowUp') {
        panY += step;
      } else if (event.key === 'ArrowDown') {
        panY -= step;
      }
    };

    resize();
    drawFrame();
    const observer = new ResizeObserver(resize);
    observer.observe(canvas.parentElement || canvas);
    canvas.addEventListener('pointerdown', onPointerDown);
    canvas.addEventListener('pointermove', onPointerMove);
    canvas.addEventListener('pointerup', onPointerUp);
    canvas.addEventListener('pointercancel', onPointerUp);
    canvas.addEventListener('contextmenu', onContextMenu);
    canvas.addEventListener('click', onClick);
    canvas.addEventListener('dblclick', onDblClick);
    canvas.addEventListener('wheel', onWheel, { passive: false });
    window.addEventListener('keydown', onKeyDown);

    return () => {
      cancelAnimationFrame(raf);
      observer.disconnect();
      canvas.removeEventListener('pointerdown', onPointerDown);
      canvas.removeEventListener('pointermove', onPointerMove);
      canvas.removeEventListener('pointerup', onPointerUp);
      canvas.removeEventListener('pointercancel', onPointerUp);
      canvas.removeEventListener('contextmenu', onContextMenu);
      canvas.removeEventListener('click', onClick);
      canvas.removeEventListener('dblclick', onDblClick);
      canvas.removeEventListener('wheel', onWheel);
      window.removeEventListener('keydown', onKeyDown);
    };
  }, [nodes, edges, selectedAssetId, mode, onSelect, enterOrigin]);

  return (
    <div className="lineage-universe-scene">
      <canvas ref={canvasRef} className="lineage-universe-canvas" />
      <div ref={overlayRef} className="lineage-universe-hud-card" data-visible="0" />
      <div className="lineage-universe-toolbar" role="toolbar" aria-label="Навигация Universe">
        <Segmented
          size="small"
          value={tool}
          onChange={(value) => setTool(value as DragTool)}
          options={[
            {
              value: 'pan',
              icon: (
                <Tooltip title="Move — перетаскивание сдвигает сцену">
                  <span className="lineage-universe-toolbar__seg">
                    <DragOutlined /> Move
                  </span>
                </Tooltip>
              ),
            },
            {
              value: 'orbit',
              icon: (
                <Tooltip title="Orbit — перетаскивание вращает сцену">
                  <span className="lineage-universe-toolbar__seg">
                    <RetweetOutlined /> Orbit
                  </span>
                </Tooltip>
              ),
            },
          ]}
        />
        <Space.Compact size="small">
          <Tooltip title="Zoom out (−)">
            <Button
              icon={<MinusOutlined />}
              aria-label="Zoom out"
              onClick={() => controlsRef.current.zoomOut()}
            />
          </Tooltip>
          <Tooltip title="Zoom in (+)">
            <Button
              icon={<PlusOutlined />}
              aria-label="Zoom in"
              onClick={() => controlsRef.current.zoomIn()}
            />
          </Tooltip>
        </Space.Compact>
        <Space.Compact size="small">
          <Tooltip title="Сдвинуть влево">
            <Button aria-label="Pan left" onClick={() => controlsRef.current.nudge(48, 0)}>
              ←
            </Button>
          </Tooltip>
          <Tooltip title="Сдвинуть вверх">
            <Button aria-label="Pan up" onClick={() => controlsRef.current.nudge(0, 48)}>
              ↑
            </Button>
          </Tooltip>
          <Tooltip title="Сдвинуть вниз">
            <Button aria-label="Pan down" onClick={() => controlsRef.current.nudge(0, -48)}>
              ↓
            </Button>
          </Tooltip>
          <Tooltip title="Сдвинуть вправо">
            <Button aria-label="Pan right" onClick={() => controlsRef.current.nudge(-48, 0)}>
              →
            </Button>
          </Tooltip>
        </Space.Compact>
        <Tooltip title="Сбросить вид (Home)">
          <Button
            size="small"
            icon={<ReloadOutlined />}
            aria-label="Reset view"
            onClick={() => controlsRef.current.resetView()}
          >
            Reset
          </Button>
        </Tooltip>
        <Tooltip title="Двойной клик по узлу — центр камеры на нём">
          <span className="lineage-universe-toolbar__hint">
            <AimOutlined /> 2× клик = центр
          </span>
        </Tooltip>
      </div>
    </div>
  );
};

export default LineageUniverseScene;
