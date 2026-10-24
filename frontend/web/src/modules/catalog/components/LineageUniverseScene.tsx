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
import { useEffect, useRef, useState, type MutableRefObject } from 'react';
import { STAGE_ORDER, TYPE_ACCENT, buildFlowEdges } from './lineageFlow';
import './lineageUniverse.css';

export type UniverseOrigin = { x: number; y: number; z: number };

export type UniverseSceneControls = {
  zoomIn: () => void;
  zoomOut: () => void;
  resetView: () => void;
  nudge: (dx: number, dy: number) => void;
  flyTo: (assetId: string) => void;
  flyToLetter: (letter: string) => void;
};

type Props = {
  nodes: LineageNode[];
  edges: LineageEdge[];
  selectedAssetId?: string;
  /** Roots catalogue: open a source chain. Asset chain: open object card. */
  mode: 'roots' | 'chain';
  /** World point of the clicked ring node — animates chain unfold from here. */
  enterOrigin?: UniverseOrigin | null;
  /** Highlight this asset from the results list (no camera move). */
  focusAssetId?: string | null;
  /** Optional handle for search rail / letter chips. */
  sceneApiRef?: MutableRefObject<UniverseSceneControls | null>;
  onSelect?: (assetId: string, origin?: UniverseOrigin) => void;
  /** Clear search / selection in the page chrome (Reset). */
  onReset?: () => void;
  /** Active kind filter from the page (badge highlight). */
  kindFilter?: string | null;
  /** Click kind badge → filter catalogue by that kind (toggle). */
  onFilterKind?: (kind: string) => void;
  /**
   * Roots idle: stable ids currently in the front observation cone
   * (debounced / hysteresis — safe for a React list without flicker).
   */
  onFrontParade?: (assetIds: string[]) => void;
};

type DragTool = 'orbit' | 'pan';

type SceneControls = UniverseSceneControls;

type SectionGuide = {
  label: string;
  x: number;
  y: number;
  z: number;
  /** Island core (fly-to target); badge may sit outward. */
  coreX: number;
  coreZ: number;
  count?: number;
};

type GuideHit = {
  label: string;
  x: number;
  y: number;
  w: number;
  h: number;
  z: number;
};

const letterBucket = (name: string): string => {
  const ch = (name || '?').trim().charAt(0).toLocaleUpperCase('en-US');
  if (ch >= 'A' && ch <= 'Z') {
    return ch;
  }
  return '#';
};

/**
 * Prototype of future data_source_items.kind
 * (e.g. «Котировки», «Внутренний рынок», «Экспорт», «Производство»).
 * Missing → single «Прочее» island.
 */
const kindBucket = (node: LineageNode): string => {
  const raw = node.kind?.trim();
  return raw ? raw.toLocaleLowerCase('ru-RU') : 'прочее';
};

type DownstreamStats = {
  extraction: number;
  process: number;
  table: number;
  view: number;
};

const statsFromNode = (node: LineageNode): DownstreamStats | null => {
  if (
    node.extraction_source_count == null &&
    node.process_count == null &&
    node.table_count == null &&
    node.view_count == null
  ) {
    return null;
  }
  return {
    extraction: node.extraction_source_count ?? 0,
    process: node.process_count ?? 0,
    table: node.table_count ?? 0,
    view: node.view_count ?? 0,
  };
};

/** Soft mass for log sizing — extractions weigh most. */
const statsMass = (stats: DownstreamStats | null | undefined) => {
  if (!stats) {
    return 0;
  }
  return stats.extraction + stats.process * 0.5 + stats.table * 0.25 + stats.view * 0.25;
};

/** log1p boost capped so giants stay readable next to small sources. */
const logSizeBoost = (mass: number, maxBoost = 14) =>
  Math.min(maxBoost, 4.2 * Math.log1p(Math.max(0, mass)));

const formatStatsLine = (stats: DownstreamStats | null | undefined) => {
  if (!stats) {
    return '';
  }
  const bits: string[] = [];
  if (stats.extraction) {
    bits.push(`${stats.extraction} EXTRACTION`);
  }
  if (stats.process) {
    bits.push(`${stats.process} PROCESS`);
  }
  if (stats.table) {
    bits.push(`${stats.table} TABLE`);
  }
  if (stats.view) {
    bits.push(`${stats.view} VIEW`);
  }
  return bits.length ? bits.join(' · ') : 'нет downstream';
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
  stats?: DownstreamStats | null;
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
/** Roots catalogue: one full cloud turn (oblique view stays fixed). */
const ROOTS_CLOUD_SPIN_MS = 180_000;
/** Resume auto-spin this long after the last Move (pan/nudge). */
const ROOTS_SPIN_RESUME_MS = 10_000;
const ROOTS_VIEW_YAW = 0.72;
const ROOTS_VIEW_PITCH = 0.48;
/** Shift cloud left — right side has the names filter overlay. */
const ROOTS_UI_RIGHT_PAD_PX = 168;
/** Slight screen lift (panY down-positive → negative = higher). */
const ROOTS_UI_NUDGE_UP_PX = 54;

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
/** Stronger perspective on roots turntable — front islands read closer. */
const FOCAL_ROOTS = 640;
const DRAG = 0.88;
const HOME_PULL = 0.055;
const CHARGE = 1100;
/** Same cyan as KIND chip border — tint for the active kind spiral. */
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
  focusAssetId = null,
  sceneApiRef,
  onSelect,
  onReset,
  kindFilter = null,
  onFilterKind,
  onFrontParade,
}: Props) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const overlayRef = useRef<HTMLDivElement>(null);
  const toolRef = useRef<DragTool>('orbit');
  const controlsRef = useRef<SceneControls>({
    zoomIn: () => undefined,
    zoomOut: () => undefined,
    resetView: () => undefined,
    nudge: () => undefined,
    flyTo: () => undefined,
    flyToLetter: () => undefined,
  });
  /** List hover/keyboard highlight — visual only; camera moves via flyTo / flyToLetter. */
  const highlightRef = useRef<string | null>(null);
  highlightRef.current = focusAssetId ?? null;
  const kindFilterRef = useRef<string | null>(kindFilter);
  kindFilterRef.current = kindFilter;
  const onFrontParadeRef = useRef(onFrontParade);
  onFrontParadeRef.current = onFrontParade;
  const [tool, setTool] = useState<DragTool>('orbit');
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
      ring?: { angle: number; radius: number },
      statsOverride?: DownstreamStats | null
    ) => {
      const stats = statsOverride ?? statsFromNode(node);
      const base =
        shell === 0
          ? 22
          : shell === 1
            ? 16
            : shell >= 4
              ? 14
              : node.asset_type === 'PROCESS'
                ? 15
                : 13;
      // Nuclei (shell 0): log-scale by downstream mass; other shells stay fixed.
      const size = shell === 0 ? base + logSizeBoost(statsMass(stats)) : base;
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
        stats,
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

    const sectionGuides: SectionGuide[] = [];

    if (mode === 'roots') {
      // Kind islands: group by LineageNode.kind (prototype of data_source_items.kind).
      // Each island is a small Vogel spiral; islands sit on a ring by kind order.
      const catalogue = [
        ...hubList.map((id) => byId.get(id)).filter((node): node is LineageNode => Boolean(node)),
        ...orphanIds
          .map((id) => byId.get(id))
          .filter((node): node is LineageNode => Boolean(node)),
      ];
      const byKind = new Map<string, LineageNode[]>();
      for (const node of catalogue) {
        const key = kindBucket(node);
        const list = byKind.get(key) ?? [];
        list.push(node);
        byKind.set(key, list);
      }
      const kindKeys = [...byKind.keys()].sort((a, b) => {
        if (a === 'прочее') return 1;
        if (b === 'прочее') return -1;
        return a.localeCompare(b, 'ru');
      });
      const kindDisplay = new Map<string, string>();
      for (const key of kindKeys) {
        const group = byKind.get(key) ?? [];
        group.sort(
          (a, b) =>
            a.display_name.localeCompare(b.display_name, 'ru') ||
            a.id.localeCompare(b.id)
        );
        const labeled = group.find((node) => node.kind?.trim())?.kind?.trim();
        kindDisplay.set(key, labeled || (key === 'прочее' ? 'Прочее' : key));
      }
      const islandCount = Math.max(1, kindKeys.length);
      const maxIslandSize = Math.max(
        1,
        ...kindKeys.map((key) => byKind.get(key)?.length ?? 0)
      );
      const hasTypedKinds = catalogue.some((node) => Boolean(node.kind?.trim()));
      // Multi-island archipelago vs one focused kind spiral (filter / no kinds).
      const soloIsland = islandCount === 1;
      const archipelagoPacking =
        maxIslandSize <= 20 ? 92 : maxIslandSize <= 50 ? 78 : 66;
      const goldenAngle = Math.PI * (3 - Math.sqrt(5));
      const islandOrbit = soloIsland
        ? 0
        : 300 +
          Math.sqrt(maxIslandSize) * archipelagoPacking * 1.2 +
          Math.max(0, islandCount - 4) * 56;
      kindKeys.forEach((key, kindIndex) => {
        const group = byKind.get(key) ?? [];
        const n = Math.max(1, group.length);
        // Solo: expand packing so the subgroup fills free stage space.
        const targetExtent = soloIsland
          ? n <= 6
            ? 320
            : n <= 15
              ? 480
              : n <= 30
                ? 620
                : n <= 55
                  ? 760
                  : 900
          : archipelagoPacking * Math.sqrt(n + 0.35);
        const packing = soloIsland
          ? Math.max(56, targetExtent / Math.sqrt(n + 0.35))
          : archipelagoPacking;
        const angle =
          soloIsland
            ? 0
            : (kindIndex / islandCount) * Math.PI * 2 - Math.PI / 2;
        const cx = Math.cos(angle) * islandOrbit;
        const cz = Math.sin(angle) * islandOrbit;
        const islandExtent = packing * Math.sqrt(n + 0.35);
        // A bit further outside the rim so chips don't sit on cores.
        const rimPad = soloIsland ? 120 : 140;
        const outward =
          islandOrbit > 1 ? 1 + (islandExtent + rimPad) / islandOrbit : 1.18;
        // KIND chips only when at least one node carries a real kind.
        if (hasTypedKinds) {
          sectionGuides.push({
            label: kindDisplay.get(key) ?? key,
            x: soloIsland ? 0 : cx * outward,
            y: soloIsland ? islandExtent * 0.06 + 22 : 14,
            z: soloIsland ? -islandExtent - rimPad : cz * outward,
            coreX: cx,
            coreZ: cz,
            count: group.length,
          });
        }
        group.forEach((node, index) => {
          const radius = packing * Math.sqrt(index + 0.35);
          const theta = index * goldenAngle;
          const x = cx + Math.cos(theta) * radius;
          const z = cz + Math.sin(theta) * radius;
          const y = Math.sin(index * 1.7 + kindIndex) * (soloIsland ? 14 : 10);
          const isHub = hubIds.has(node.id);
          placeAt(
            node,
            isHub ? 0 : shellForType(node.asset_type),
            isHub ? node.id : null,
            x,
            y,
            z
          );
        });
      });
      // Recenter archipelago on bbox middle so spin/camera share one axis.
      if (bodies.length) {
        let minX = Infinity;
        let maxX = -Infinity;
        let minZ = Infinity;
        let maxZ = -Infinity;
        for (const body of bodies) {
          minX = Math.min(minX, body.homeX);
          maxX = Math.max(maxX, body.homeX);
          minZ = Math.min(minZ, body.homeZ);
          maxZ = Math.max(maxZ, body.homeZ);
        }
        const midX = (minX + maxX) / 2;
        const midZ = (minZ + maxZ) / 2;
        if (Math.abs(midX) > 0.5 || Math.abs(midZ) > 0.5) {
          for (const body of bodies) {
            body.homeX -= midX;
            body.homeZ -= midZ;
            body.x -= midX;
            body.z -= midZ;
          }
          for (const guide of sectionGuides) {
            guide.x -= midX;
            guide.z -= midZ;
            guide.coreX -= midX;
            guide.coreZ -= midZ;
          }
        }
      }
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
        // Lane "hub" is a layout root, not always DATA_SOURCE — when search
        // drops sources, EXTRACTION_SOURCE may be promoted. Keep stage by type.
        const shell = shellForType(node.asset_type);
        const memberStats: DownstreamStats = {
          extraction: 0,
          process: 0,
          table: 0,
          view: 0,
        };
        for (const memberId of members.get(id) ?? []) {
          const member = byId.get(memberId);
          if (!member) {
            continue;
          }
          if (member.asset_type === 'EXTRACTION_SOURCE') {
            memberStats.extraction += 1;
          } else if (member.asset_type === 'PROCESS') {
            memberStats.process += 1;
          } else if (member.asset_type === 'TABLE') {
            memberStats.table += 1;
          } else if (member.asset_type === 'VIEW') {
            memberStats.view += 1;
          }
        }
        placeAt(
          node,
          shell,
          id,
          FLOW_STAGE_X[shell] ?? FLOW_STAGE_X[0],
          0,
          lane.z,
          undefined,
          undefined,
          memberStats
        );
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
    // Fixed layout poses — roots cloud spins by rotating these around Y.
    const bodyLayout = new Map(
      bodies.map((body) => [body.id, { x: body.homeX, z: body.homeZ }] as const)
    );
    const guideLayout = sectionGuides.map((guide) => ({
      x: guide.x,
      y: guide.y,
      z: guide.z,
      coreX: guide.coreX,
      coreZ: guide.coreZ,
    }));
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
    let yaw = mode === 'roots' ? ROOTS_VIEW_YAW : 0.02;
    let pitch = mode === 'roots' ? ROOTS_VIEW_PITCH : 0.82;
    let cloudSpin = 0;
    let lastSpinNow = 0;
    let spinHoldUntil = 0;
    const holdCloudSpin = (ms = ROOTS_SPIN_RESUME_MS) => {
      spinHoldUntil = Math.max(spinHoldUntil, performance.now() + ms);
    };
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
    let hoverGuide: string | null = null;
    let spotlightKind: string | null = null;
    /** Front-cone parade → right rail (hysteresis + interval). */
    const paradeHits = new Map<string, number>();
    const paradeMisses = new Map<string, number>();
    /** When an id first joined the stable parade — newest → top of the list. */
    const paradeEnteredAt = new Map<string, number>();
    let paradeStable: string[] = [];
    let paradeKey = '';
    let paradeLastEmit = 0;
    const PARADE_INTERVAL_MS = 520;
    const PARADE_ENTER = 2;
    const PARADE_EXIT = 3;
    const PARADE_MAX = 8;
    let focusId: string | null = selectedAssetId ?? hubList[0] ?? bodies[0]?.id ?? null;
    let pulse = 0;
    let raf = 0;
    let hits: ScreenHit[] = [];
    let guideHits: GuideHit[] = [];
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

    // Pivot = bbox center of layout (drawing area). Layout was recentered to ~0.
    const cloudPivot = (() => {
      if (!bodies.length || mode !== 'roots') {
        return { x: 0, z: 0 };
      }
      let minX = Infinity;
      let maxX = -Infinity;
      let minZ = Infinity;
      let maxZ = -Infinity;
      for (const pose of bodyLayout.values()) {
        minX = Math.min(minX, pose.x);
        maxX = Math.max(maxX, pose.x);
        minZ = Math.min(minZ, pose.z);
        maxZ = Math.max(maxZ, pose.z);
      }
      if (!Number.isFinite(minX)) {
        return { x: 0, z: 0 };
      }
      return { x: (minX + maxX) / 2, z: (minZ + maxZ) / 2 };
    })();

    const applyCloudSpin = (angle: number) => {
      if (mode !== 'roots') {
        return;
      }
      const cos = Math.cos(angle);
      const sin = Math.sin(angle);
      const px = cloudPivot.x;
      const pz = cloudPivot.z;
      for (const body of bodies) {
        const base = bodyLayout.get(body.id);
        if (!base) {
          continue;
        }
        const lx = base.x - px;
        const lz = base.z - pz;
        const nx = px + lx * cos - lz * sin;
        const nz = pz + lx * sin + lz * cos;
        const dx = nx - body.homeX;
        const dz = nz - body.homeZ;
        body.homeX = nx;
        body.homeZ = nz;
        body.x += dx;
        body.z += dz;
      }
      sectionGuides.forEach((guide, index) => {
        const base = guideLayout[index];
        if (!base) {
          return;
        }
        const lx = base.x - px;
        const lz = base.z - pz;
        guide.x = px + lx * cos - lz * sin;
        guide.z = pz + lx * sin + lz * cos;
        guide.y = base.y;
        const cx = base.coreX - px;
        const cz = base.coreZ - pz;
        guide.coreX = px + cx * cos - cz * sin;
        guide.coreZ = pz + cx * sin + cz * cos;
      });
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
        // Full galaxy vs focused kind spiral — zoom from content size.
        yaw = ROOTS_VIEW_YAW;
        pitch = ROOTS_VIEW_PITCH;
        applyCloudSpin(cloudSpin);
        recomputeFieldBounds();
        let maxR = 0;
        let hy = 0;
        for (const body of bodies) {
          maxR = Math.max(
            maxR,
            Math.hypot(body.homeX - cloudPivot.x, body.homeZ - cloudPivot.z)
          );
          hy += body.homeY;
        }
        hy /= Math.max(1, bodies.length);
        const solo =
          Boolean(kindFilterRef.current) || sectionGuides.length <= 1;
        const span = solo
          ? Math.max(420, maxR * 2.2 + 140)
          : Math.max(1100, maxR * 2.15 + 420);
        const fill = solo ? 0.86 : 0.68;
        const zoomMin = solo ? 0.38 : 0.28;
        const zoomMax = solo ? 1.55 : 0.78;
        targetZoom = clamp(
          (Math.min(width, height) * fill) / span,
          zoomMin,
          zoomMax
        );
        targetLookX = cloudPivot.x;
        targetLookY = hy;
        targetLookZ = cloudPivot.z;
        panX = -Math.min(ROOTS_UI_RIGHT_PAD_PX, width * 0.18);
        panY = -ROOTS_UI_NUDGE_UP_PX;
        endLookX = targetLookX;
        endLookY = targetLookY;
        endLookZ = targetLookZ;
        endZoom = targetZoom;
        endYaw = yaw;
        endPitch = pitch;
        if (snap) {
          lookX = cloudPivot.x;
          lookY = hy;
          lookZ = cloudPivot.z;
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

    const flyToBody = (id: string | null, closeUp = false) => {
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
      panX *= 0.2;
      panY *= 0.2;
      if (mode === 'roots' || closeUp) {
        targetZoom = Math.max(targetZoom, closeUp ? 1.35 : 1.05);
      }
    };

    const flyToKind = (label: string) => {
      const key = label.trim().toLocaleLowerCase('ru-RU');
      const guide = sectionGuides.find(
        (item) =>
          item.label === label || item.label.toLocaleLowerCase('ru-RU') === key
      );
      if (!guide) {
        return;
      }
      followFocus = false;
      userAdjustedView = true;
      holdCloudSpin();
      targetLookX = guide.coreX;
      targetLookY = 40;
      targetLookZ = guide.coreZ;
      targetZoom = clamp(
        (Math.min(width, height) * 0.72) /
          Math.max(420, Math.sqrt(guide.count ?? 12) * 95 + 220),
        0.7,
        1.55
      );
      panX = -Math.min(ROOTS_UI_RIGHT_PAD_PX * 0.65, width * 0.1);
      panY = -ROOTS_UI_NUDGE_UP_PX * 0.7;
    };

    const flyToLetter = (letter: string) => {
      const key = letter.trim().toLocaleLowerCase('en-US');
      const guide = sectionGuides.find(
        (item) =>
          item.label === letter ||
          item.label.toLocaleLowerCase('ru-RU') === key ||
          item.label.toLocaleLowerCase('en-US') === key ||
          item.label.toLocaleUpperCase('en-US') === letter.toUpperCase()
      );
      if (guide) {
        flyToKind(guide.label);
        return;
      }
      const first = bodies.find(
        (body) => letterBucket(body.label) === letter.toUpperCase()
      );
      flyToBody(first?.id ?? null, true);
    };

    const project = (x: number, y: number, z: number, focal = FOCAL) => {
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
      const depth = focal / (focal + z2 * zoom);
      return {
        x: width / 2 + panX + x1 * depth * zoom,
        y: height / 2 + panY + y1 * depth * zoom * 0.92,
        depth,
        z: z2,
      };
    };

    const projectScene = (x: number, y: number, z: number) =>
      project(x, y, z, mode === 'roots' ? FOCAL_ROOTS : FOCAL);

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

    const hitTestGuide = (mx: number, my: number): string | null => {
      let best: GuideHit | null = null;
      for (const hit of guideHits) {
        if (
          mx >= hit.x - hit.w / 2 &&
          mx <= hit.x + hit.w / 2 &&
          my >= hit.y - hit.h / 2 &&
          my <= hit.y + hit.h / 2
        ) {
          if (!best || hit.z < best.z) {
            best = hit;
          }
        }
      }
      return best?.label ?? null;
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

    const drawLabel = (
      text: string,
      x: number,
      y: number,
      emphasis: boolean,
      opts?: { alpha?: number; fontSize?: number }
    ) => {
      const alpha = opts?.alpha ?? 1;
      const fontSize = opts?.fontSize ?? (emphasis ? 13 : 12);
      ctx.save();
      ctx.globalAlpha = Math.max(0, Math.min(1, alpha));
      ctx.font = `${emphasis ? 600 : 500} ${fontSize}px "Segoe UI", system-ui, sans-serif`;
      const widthText = ctx.measureText(text).width;
      const padX = 8;
      const boxW = widthText + padX * 2;
      const boxH = Math.max(22, fontSize + 10);
      const left = x - boxW / 2;
      const top = y;
      ctx.fillStyle = emphasis ? 'rgba(15, 23, 42, 0.55)' : 'rgba(8, 12, 24, 0.22)';
      ctx.strokeStyle = emphasis ? 'rgba(125, 211, 252, 0.45)' : 'rgba(255,255,255,0.08)';
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
      ctx.restore();
    };

    const drawFrame = () => {
      const now = performance.now();
      pulse += reduced ? 0 : 0.03;

      const listHighlight = highlightRef.current;

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

      // Roots: slow cloud turntable; after Move/Orbit, resume when spinHoldUntil elapses.
      if (
        mode === 'roots' &&
        !reduced &&
        !dragMode &&
        !followFocus &&
        !exitId &&
        !hoverGuide &&
        now >= spinHoldUntil
      ) {
        if (!lastSpinNow) {
          lastSpinNow = now;
        }
        const dt = Math.min(48, Math.max(0, now - lastSpinNow));
        lastSpinNow = now;
        cloudSpin += (dt / ROOTS_CLOUD_SPIN_MS) * Math.PI * 2;
        applyCloudSpin(cloudSpin);
      } else {
        lastSpinNow = now;
      }

      // Orbit inertia only in chain view.
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
        const p = projectScene(star.x, star.y, star.z);
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
          const p = projectScene(Math.cos(angle) * ringR, 0, Math.sin(angle) * ringR);
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
        const caption = projectScene(0, 0, -ringR - 48);
        ctx.setLineDash([]);
        ctx.font = '12px "Segoe UI", system-ui, sans-serif';
        ctx.fillStyle = 'rgba(186, 210, 255, 0.72)';
        ctx.textAlign = 'center';
        ctx.fillText('Каталог · острова по kind · клик — поток', caption.x, caption.y);
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
          const a = projectScene(stageX, 0, zTop);
          const b = projectScene(stageX, 0, zBottom);
          ctx.beginPath();
          ctx.moveTo(a.x, a.y);
          ctx.lineTo(b.x, b.y);
          ctx.strokeStyle =
            index === 0 ? 'rgba(125, 211, 252, 0.28)' : 'rgba(148, 163, 184, 0.14)';
          ctx.lineWidth = index === 0 || index === stageXs.length - 1 ? 1.4 : 1;
          ctx.setLineDash(index === 0 ? [] : [5, 10]);
          ctx.stroke();
          const labelAt = projectScene(stageX, 0, zTop - 36);
          ctx.font = '11px "Segoe UI", system-ui, sans-serif';
          ctx.fillStyle = 'rgba(186, 210, 255, 0.7)';
          ctx.textAlign = 'center';
          ctx.fillText(FLOW_STAGE_LABELS[index] ?? '', labelAt.x, labelAt.y);
        });
        const midZ = (fieldBounds.minZ + fieldBounds.maxZ) / 2;
        const flowFrom = projectScene(stageXs[0] ?? FLOW_STAGE_X[0], 0, midZ);
        const flowTo = projectScene(stageXs[LAST_STAGE] ?? FLOW_STAGE_X[LAST_STAGE], 0, midZ);
        ctx.setLineDash([]);
        ctx.strokeStyle = 'rgba(125, 211, 252, 0.22)';
        ctx.lineWidth = 1.2;
        ctx.beginPath();
        ctx.moveTo(flowFrom.x, flowFrom.y);
        ctx.lineTo(flowTo.x, flowTo.y);
        ctx.stroke();
        drawArrow(flowFrom.x, flowFrom.y, flowTo.x, flowTo.y, 'rgba(125, 211, 252, 0.55)');
        for (const lane of hubLane.values()) {
          const left = projectScene(fieldBounds.minX, 0, lane.z - lane.half + 8);
          const right = projectScene(fieldBounds.maxX, 0, lane.z - lane.half + 8);
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
            pa: projectScene(a.x, a.y, a.z),
            pb: projectScene(b.x, b.y, b.z),
          };
        })
        .filter((item): item is NonNullable<typeof item> => Boolean(item))
        .sort((left, right) => (left.pa.z + left.pb.z) / 2 - (right.pa.z + right.pb.z) / 2);

      for (const item of projectedLinks) {
        const hot =
          item.a.id === focusId ||
          item.b.id === focusId ||
          item.a.id === hoverId ||
          item.b.id === hoverId ||
          item.a.id === listHighlight ||
          item.b.id === listHighlight;
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
          const pb = projectScene(body.x, body.y, body.z);
          for (const hubId of body.bridgeHubIds) {
            const hub = bodyMap.get(hubId);
            if (!hub) {
              continue;
            }
            const ph = projectScene(hub.x, hub.y, hub.z);
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
        .map((body) => ({ body, p: projectScene(body.x, body.y, body.z) }))
        .sort((left, right) => right.p.z - left.p.z);

      let zNear = Infinity;
      let zFar = -Infinity;
      for (const item of projectedBodies) {
        if (item.p.depth <= 0.04) {
          continue;
        }
        zNear = Math.min(zNear, item.p.z);
        zFar = Math.max(zFar, item.p.z);
      }
      const zSpan = Math.max(1, zFar - zNear);
      const frontnessOf = (z: number) => clamp01((zFar - z) / zSpan);

      // Spotlight kind = island whose members dominate the front of the turntable.
      if (mode === 'roots' && projectedBodies.length) {
        const kindScore = new Map<string, number>();
        for (const { body, p } of projectedBodies) {
          if (p.depth <= 0.04) {
            continue;
          }
          const front = frontnessOf(p.z);
          if (front < 0.42) {
            continue;
          }
          const node = byId.get(body.id);
          const kind = node?.kind?.trim() || 'Прочее';
          const weight = (front - 0.42) ** 2;
          kindScore.set(kind, (kindScore.get(kind) ?? 0) + weight);
        }
        let bestKind: string | null = null;
        let bestScore = 0;
        for (const [kind, score] of kindScore) {
          if (score > bestScore) {
            bestScore = score;
            bestKind = kind;
          }
        }
        if (bestKind) {
          if (!spotlightKind) {
            spotlightKind = bestKind;
          } else if (bestKind !== spotlightKind) {
            const prevScore = kindScore.get(spotlightKind) ?? 0;
            if (bestScore > prevScore * 1.18 + 0.02) {
              spotlightKind = bestKind;
            }
          }
        }
      }

      for (const { body, p } of projectedBodies) {
        if (p.depth <= 0.04) {
          continue;
        }
        const active =
          body.id === focusId ||
          body.id === hoverId ||
          body.id === selectedAssetId ||
          body.id === listHighlight;
        const front = mode === 'roots' ? frontnessOf(p.z) : 0.5;
        const nodeKind = byId.get(body.id)?.kind?.trim() || 'Прочее';
        const cohortKind = kindFilterRef.current || spotlightKind;
        const isCurrentKind =
          mode === 'roots' && Boolean(cohortKind) && nodeKind === cohortKind;
        // Filtered spiral: all nodes; archipelago: emphasize the flying front of that kind.
        const inKindCohort =
          isCurrentKind && (Boolean(kindFilterRef.current) || front >= 0.35);
        // Keep asset-type color on the nucleus; cyan is only a kind marker ring.
        const nearPop =
          mode === 'roots' ? 1 + front * front * 0.72 + (inKindCohort ? 0.08 : 0) : 1;
        const radius = Math.max(
          10,
          body.r * p.depth * (active ? 1.35 : 1.15) * nearPop
        );
        const hitR = Math.max(mode === 'roots' ? 34 : 28, radius + (mode === 'roots' ? 22 : 18));
        hits.push({ id: body.id, x: p.x, y: p.y, r: hitR, z: p.z });
        const exitFade = exitId && body.id !== exitId ? 1 - exitT * 0.92 : 1;
        const depthFade = mode === 'roots' ? 0.35 + front * 0.65 : 1;
        const cohortFade =
          mode === 'roots' &&
          cohortKind &&
          front >= 0.35 &&
          !isCurrentKind &&
          !active
            ? 0.4
            : 1;
        ctx.globalAlpha = exitFade * depthFade * cohortFade;

        const glow = ctx.createRadialGradient(
          p.x,
          p.y,
          0,
          p.x,
          p.y,
          radius * 2.4
        );
        glow.addColorStop(0, `${body.color}88`);
        glow.addColorStop(0.4, `${body.color}28`);
        glow.addColorStop(1, `${body.color}00`);
        ctx.fillStyle = glow;
        ctx.beginPath();
        ctx.arc(p.x, p.y, radius * 2.4, 0, Math.PI * 2);
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

        if (isCurrentKind) {
          // Kind marker: hairline only — no cyan smoke cloud.
          ctx.strokeStyle = 'rgba(186, 210, 255, 0.22)';
          ctx.lineWidth = 1;
          ctx.beginPath();
          ctx.arc(p.x, p.y, radius + 6, 0, Math.PI * 2);
          ctx.stroke();
        } else if (body.shell === 0) {
          ctx.strokeStyle = `rgba(148, 163, 184,${0.16 + Math.sin(pulse * 2) * 0.05})`;
          ctx.lineWidth = 1.1;
          ctx.beginPath();
          ctx.arc(p.x, p.y, radius + 7, 0, Math.PI * 2);
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

        if (mode === 'roots') {
          // Source names only in the near-camera pass below — no ambient wall of text.
          if (active) {
            drawLabel(body.label, p.x, p.y + radius + 8, true, { alpha: 1, fontSize: 14 });
            const statsLine = formatStatsLine(body.stats);
            ctx.font = '11px "Segoe UI", system-ui, sans-serif';
            ctx.fillStyle = 'rgba(125, 211, 252, 0.95)';
            ctx.textAlign = 'center';
            ctx.textBaseline = 'top';
            let tipY = p.y + radius + 34;
            if (statsLine) {
              ctx.fillText(statsLine, p.x, tipY);
              tipY += 16;
            }
            ctx.font = '10px "Segoe UI", system-ui, sans-serif';
            ctx.fillStyle = 'rgba(255,255,255,0.78)';
            ctx.fillText('клик — открыть поток', p.x, tipY);
          }
        } else if (active || bodies.length <= 48 || zoom >= 0.75) {
          drawLabel(body.label, p.x, p.y + radius + 10, active);
          ctx.font = '10px "Segoe UI", system-ui, sans-serif';
          ctx.fillStyle = active ? 'rgba(186, 210, 255, 0.95)' : 'rgba(186, 210, 255, 0.65)';
          ctx.textAlign = 'center';
          ctx.textBaseline = 'top';
          const typeLine = body.bridgeHubIds?.length
            ? `${body.type} · bridge×${body.bridgeHubIds.length}`
            : body.type;
          ctx.fillText(typeLine, p.x, p.y + radius + 36);
          let tipY = p.y + radius + 50;
          if (active && body.shell === 0) {
            const statsLine = formatStatsLine(body.stats);
            if (statsLine) {
              ctx.fillStyle = 'rgba(125, 211, 252, 0.95)';
              ctx.fillText(statsLine, p.x, tipY);
              tipY += 14;
            }
          }
          if (active) {
            ctx.fillStyle = 'rgba(255,255,255,0.78)';
            ctx.fillText('клик — карточка · двойной — сюда', p.x, tipY);
          }
        }
        ctx.globalAlpha = 1;
      }

      // Near-camera labels + stable parade ids for the right rail.
      if (mode === 'roots' && projectedBodies.length) {
        const opticalX = width / 2 + panX;
        const MAX_NEAR_LABELS = 8;
        type ObsItem = {
          body: Body;
          p: { x: number; y: number; z: number; depth: number };
          radius: number;
          front: number;
          occluded: boolean;
          inCohort: boolean;
          alreadyLabeled: boolean;
        };
        const cohortKind = kindFilterRef.current || spotlightKind;
        const candidates: ObsItem[] = [];
        for (const { body, p } of projectedBodies) {
          if (p.depth <= 0.04) {
            continue;
          }
          const front = frontnessOf(p.z);
          // Only the nearest slice toward the camera.
          if (front < 0.72) {
            continue;
          }
          if (Math.abs(p.x - opticalX) / Math.max(width, 1) > 0.22) {
            continue;
          }
          const alreadyLabeled =
            body.id === focusId ||
            body.id === hoverId ||
            body.id === selectedAssetId ||
            body.id === listHighlight;
          const nodeKind = byId.get(body.id)?.kind?.trim() || 'Прочее';
          const inCohort = Boolean(cohortKind) && nodeKind === cohortKind;
          const radius = Math.max(
            10,
            body.r * p.depth * 1.15 * (1 + front * front * 0.72)
          );
          candidates.push({
            body,
            p,
            radius,
            front,
            occluded: false,
            inCohort,
            alreadyLabeled,
          });
        }
        // Prefer cohort + closer to camera, hard cap count.
        candidates.sort((a, b) => {
          if (a.inCohort !== b.inCohort) {
            return a.inCohort ? -1 : 1;
          }
          return a.p.z - b.p.z;
        });
        const obs = candidates.slice(0, MAX_NEAR_LABELS);

        // Publish front-cone ids to the page list (hysteresis + interval).
        {
          const frameIds = obs.map((item) => item.body.id);
          const frameSet = new Set(frameIds);
          for (const id of frameIds) {
            paradeHits.set(id, (paradeHits.get(id) ?? 0) + 1);
            paradeMisses.set(id, 0);
          }
          for (const id of new Set([...paradeStable, ...paradeHits.keys()])) {
            if (!frameSet.has(id)) {
              paradeMisses.set(id, (paradeMisses.get(id) ?? 0) + 1);
              paradeHits.set(id, 0);
            }
          }
          const nowParade = performance.now();
          if (nowParade - paradeLastEmit >= PARADE_INTERVAL_MS) {
            paradeLastEmit = nowParade;
            const next = new Set(paradeStable);
            for (const [id, hits] of paradeHits) {
              if (hits >= PARADE_ENTER) {
                next.add(id);
              }
            }
            for (const id of [...next]) {
              if ((paradeMisses.get(id) ?? 0) >= PARADE_EXIT) {
                next.delete(id);
                paradeHits.delete(id);
                paradeMisses.delete(id);
                paradeEnteredAt.delete(id);
              }
            }
            for (const id of next) {
              if (!paradeEnteredAt.has(id)) {
                paradeEnteredAt.set(id, nowParade);
              }
            }
            // Newest on-screen labels first; then by front-cone order.
            const frameRank = new Map(frameIds.map((id, index) => [id, index]));
            const ordered = [...next]
              .sort((a, b) => {
                const enteredDiff =
                  (paradeEnteredAt.get(b) ?? 0) - (paradeEnteredAt.get(a) ?? 0);
                if (enteredDiff !== 0) {
                  return enteredDiff;
                }
                return (frameRank.get(a) ?? 999) - (frameRank.get(b) ?? 999);
              })
              .slice(0, PARADE_MAX);
            for (const id of [...paradeEnteredAt.keys()]) {
              if (!next.has(id)) {
                paradeEnteredAt.delete(id);
              }
            }
            const key = ordered.join('|');
            if (key !== paradeKey) {
              paradeKey = key;
              paradeStable = ordered;
              onFrontParadeRef.current?.(ordered);
            }
          }
        }

        for (const item of obs) {
          if (item.alreadyLabeled) {
            continue; // labeled in the body pass
          }
          for (const other of projectedBodies) {
            if (other.body.id === item.body.id || other.p.depth <= 0.04) {
              continue;
            }
            if (other.p.z >= item.p.z) {
              continue;
            }
            const otherFront = frontnessOf(other.p.z);
            const otherR = Math.max(
              10,
              other.body.r * other.p.depth * 1.15 * (1 + otherFront * otherFront * 0.72)
            );
            const dist = Math.hypot(other.p.x - item.p.x, other.p.y - item.p.y);
            if (dist < otherR + item.radius * 0.55) {
              item.occluded = true;
              break;
            }
          }
        }
        const labelObs = obs.filter((item) => !item.alreadyLabeled);
        labelObs.sort((a, b) => b.p.z - a.p.z);
        for (const item of labelObs) {
          const fontSize = item.inCohort
            ? item.occluded
              ? 15
              : 13 + item.front
            : item.occluded
              ? 13
              : 12;
          drawLabel(item.body.label, item.p.x, item.p.y + item.radius + 8, true, {
            alpha: item.inCohort
              ? item.occluded
                ? 0.9
                : 0.8
              : item.occluded
                ? 0.8
                : 0.65,
            fontSize,
          });
          if (item.occluded || item.inCohort) {
            ctx.save();
            ctx.globalAlpha = item.inCohort ? 0.28 : 0.4;
            ctx.strokeStyle = item.inCohort
              ? 'rgba(186, 210, 255, 0.28)'
              : 'rgba(148, 163, 184, 0.35)';
            ctx.lineWidth = 1;
            ctx.setLineDash(item.inCohort ? [] : [3, 4]);
            ctx.beginPath();
            ctx.arc(item.p.x, item.p.y, item.radius + 5, 0, Math.PI * 2);
            ctx.stroke();
            ctx.setLineDash([]);
            ctx.restore();
          }
        }
      }

      // Kind chips — separate from source labels; click = filter by kind.
      guideHits = [];
      if (mode === 'roots' && sectionGuides.length) {
        const activeKind = kindFilterRef.current;
        const guidesProjected = sectionGuides
          .map((guide) => ({ guide, p: projectScene(guide.x, guide.y, guide.z) }))
          .filter((item) => item.p.depth > 0.05)
          .sort((a, b) => b.p.z - a.p.z);
        for (const { guide, p } of guidesProjected) {
          const filtered = activeKind === guide.label;
          const lit = filtered || spotlightKind === guide.label;
          const hovered = hoverGuide === guide.label;
          const tag = 'KIND';
          const title = guide.count ? `${guide.label} · ${guide.count}` : guide.label;
          const size = Math.max(12, Math.min(filtered ? 17 : lit ? 16 : 14, 15 * p.depth));
          ctx.font = `700 ${size}px "Segoe UI", system-ui, sans-serif`;
          const titleW = ctx.measureText(title).width;
          ctx.font = `700 ${Math.max(9, size - 3)}px "Segoe UI", system-ui, sans-serif`;
          const tagW = ctx.measureText(tag).width;
          const gap = 8;
          const padX = 10;
          const padY = 6;
          const boxW = tagW + gap + titleW + padX * 2 + 6;
          const boxH = size + padY * 2 + 2;
          const left = p.x - boxW / 2;
          const top = p.y - boxH / 2;
          guideHits.push({
            label: guide.label,
            x: p.x,
            y: p.y,
            w: boxW + 10,
            h: boxH + 10,
            z: p.z,
          });
          ctx.save();
          ctx.globalAlpha = Math.min(
            0.95,
            (filtered ? 0.88 : lit ? 0.7 : 0.42) * (hovered ? 1.1 : 1)
          );
          ctx.fillStyle = filtered
            ? 'rgba(30, 64, 90, 0.78)'
            : lit
              ? 'rgba(30, 58, 95, 0.68)'
              : 'rgba(15, 23, 42, 0.55)';
          ctx.strokeStyle = filtered
            ? 'rgba(148, 163, 184, 0.45)'
            : lit
              ? 'rgba(148, 163, 184, 0.4)'
              : hovered
                ? 'rgba(186, 210, 255, 0.45)'
                : 'rgba(100, 116, 139, 0.35)';
          ctx.lineWidth = filtered ? 1.5 : lit ? 1.4 : 1.2;
          if (typeof ctx.roundRect === 'function') {
            ctx.beginPath();
            ctx.roundRect(left, top, boxW, boxH, 9);
            ctx.fill();
            ctx.stroke();
          } else {
            ctx.fillRect(left, top, boxW, boxH);
            ctx.strokeRect(left, top, boxW, boxH);
          }
          // Accent bar — visually separate from source name pills.
          ctx.fillStyle = filtered
            ? 'rgba(148, 163, 184, 0.45)'
            : 'rgba(100, 116, 139, 0.45)';
          ctx.fillRect(left + 3, top + 4, 3, boxH - 8);
          const textX = left + padX + 6;
          ctx.textAlign = 'left';
          ctx.textBaseline = 'middle';
          ctx.font = `700 ${Math.max(9, size - 3)}px "Segoe UI", system-ui, sans-serif`;
          ctx.fillStyle = 'rgba(186, 210, 255, 0.85)';
          ctx.fillText(tag, textX, p.y);
          ctx.font = `700 ${size}px "Segoe UI", system-ui, sans-serif`;
          ctx.fillStyle = filtered
            ? 'rgba(255, 255, 255, 0.98)'
            : 'rgba(240, 253, 250, 0.92)';
          ctx.fillText(title, textX + tagW + gap, p.y);
          ctx.restore();
        }
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

      if (hoverGuide) {
        const guide = sectionGuides.find((item) => item.label === hoverGuide);
        const active = kindFilterRef.current === hoverGuide;
        overlay.dataset.visible = '1';
        overlay.innerHTML = `<strong>${hoverGuide}</strong><span>KIND · ${
          guide?.count ?? '—'
        } источников</span><em>фильтр каталога</em><small>${
          active ? 'Клик — снять фильтр kind' : 'Клик — фильтр только по этому kind'
        }</small>`;
      } else {
        const tipId = hoverId ?? listHighlight ?? focusId;
        const tip = tipId ? byId.get(tipId) : null;
        const tipBody = tipId ? bodyMap.get(tipId) : null;
        if (tip) {
          overlay.dataset.visible = '1';
          const bridgeNames = (tipBody?.bridgeHubIds ?? [])
            .map((id) => byId.get(id)?.display_name || id)
            .join(' · ');
          const statsLine =
            formatStatsLine(tipBody?.stats) ||
            formatStatsLine(statsFromNode(tip));
          const action =
            mode === 'roots'
              ? 'Кликните, чтобы раскрыть поток источника слева направо'
              : tipBody?.bridgeHubIds?.length
                ? `Мост между источниками: ${bridgeNames}`
                : 'Кликните, чтобы открыть карточку объекта';
          const kindBit = tip.kind?.trim() ? ` · ${tip.kind.trim()}` : '';
          const statsBit = statsLine
            ? `<em class="lineage-universe-hud-stats">${statsLine}</em>`
            : `<em>${tip.qualified_name || tip.id}</em>`;
          const qnBit = statsLine
            ? `<em>${tip.qualified_name || tip.id}</em>`
            : '';
          overlay.innerHTML = `<strong>${tip.display_name}</strong><span>${tip.asset_type}${kindBit}${
            tipBody?.bridgeHubIds?.length ? ' · BRIDGE' : ''
          }</span>${statsBit}${qnBit}<small>${action}</small>`;
        } else {
          overlay.dataset.visible = '0';
        }
      }

      raf = requestAnimationFrame(drawFrame);
    };

    const resetView = () => {
      // Back to the default galaxy: no selection, spin at 0, overview framing.
      focusId = null;
      followFocus = false;
      exitId = null;
      userAdjustedView = false;
      spinHoldUntil = 0;
      lastSpinNow = 0;
      cloudSpin = 0;
      applyCloudSpin(0);
      fitScene(true);
      onReset?.();
    };

    const minZoom = mode === 'roots' ? 0.18 : 0.45;

    controlsRef.current = {
      zoomIn: () => {
        targetZoom = Math.min(2.4, targetZoom * 1.14);
      },
      zoomOut: () => {
        targetZoom = Math.max(minZoom, targetZoom / 1.14);
      },
      resetView,
      nudge: (dx, dy) => {
        userAdjustedView = true;
        if (mode === 'roots') {
          holdCloudSpin();
        }
        panX += dx;
        panY += dy;
      },
      flyTo: (assetId: string) => flyToBody(assetId, true),
      flyToLetter,
    };
    if (sceneApiRef) {
      sceneApiRef.current = controlsRef.current;
    }

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
      const mx = event.clientX - rect.left;
      const my = event.clientY - rect.top;
      hoverGuide = mode === 'roots' ? hitTestGuide(mx, my) : null;
      hoverId = hoverGuide ? null : hitTest(mx, my);
      const idleCursor = toolRef.current === 'pan' ? 'move' : 'grab';
      canvas.style.cursor = hoverGuide || hoverId
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
        if (mode === 'roots') {
          holdCloudSpin();
        }
        panX += dx;
        panY += dy;
        return;
      }
      if (mode === 'roots') {
        // Orbit = turn the galaxy around its center (not camera yaw).
        cloudSpin += dx * 0.0065;
        applyCloudSpin(cloudSpin);
        holdCloudSpin();
        return;
      }
      yaw += dx * 0.004;
      pitch = Math.max(-1.05, Math.min(1.15, pitch + dy * 0.0035));
      velYaw = Math.max(-0.00035, Math.min(0.00035, dx * 0.00008));
      velPitch = Math.max(-0.0002, Math.min(0.0002, dy * 0.00005));
    };
    const onPointerUp = (event: PointerEvent) => {
      if (mode === 'roots' && (dragMode === 'pan' || dragMode === 'rotate')) {
        holdCloudSpin();
      }
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
      const mx = event.clientX - rect.left;
      const my = event.clientY - rect.top;
      const kindLabel = mode === 'roots' ? hitTestGuide(mx, my) : null;
      if (kindLabel) {
        onFilterKind?.(kindLabel);
        return;
      }
      const id = hitTest(mx, my);
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
      targetZoom = Math.max(
        minZoom,
        Math.min(2.4, targetZoom * (event.deltaY > 0 ? 0.92 : 1.08))
      );
    };
    const onKeyDown = (event: KeyboardEvent) => {
      const target = event.target;
      if (
        target instanceof HTMLElement &&
        (target.tagName === 'INPUT' ||
          target.tagName === 'TEXTAREA' ||
          target.isContentEditable)
      ) {
        return;
      }
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
      if (sceneApiRef) {
        sceneApiRef.current = null;
      }
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
  }, [
    nodes,
    edges,
    selectedAssetId,
    mode,
    onSelect,
    onReset,
    onFilterKind,
    enterOrigin,
    sceneApiRef,
  ]);

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
                <Tooltip title="Orbit — в каталоге крутит галактику, в потоке — камеру">
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
