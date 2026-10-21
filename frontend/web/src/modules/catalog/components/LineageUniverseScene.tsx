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

type Props = {
  nodes: LineageNode[];
  edges: LineageEdge[];
  selectedAssetId?: string;
  /** Roots catalogue: open a source chain. Asset chain: open object card. */
  mode: 'roots' | 'chain';
  onSelect?: (assetId: string) => void;
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

type Link = {
  id: string;
  source: string;
  target: string;
  label: string;
};

type Star = { x: number; y: number; z: number; s: number };
type ScreenHit = { id: string; x: number; y: number; r: number; z: number };

const FOCAL = 820;
const DRAG = 0.86;
const HOME_PULL = 0.038;
const CHARGE = 2200;

const shellForType = (type: string): number => {
  if (type === 'DATA_SOURCE') return 0;
  if (type === 'EXTRACTION_SOURCE') return 1;
  if (type === 'STORAGE_LOCATION') return 2;
  if (type === 'PROCESS') return 3;
  return 4;
};

/** Landscape-first grid so hubs fill a rectangular field instead of a tight ring. */
const hubGridDims = (count: number, aspect = 1.6) => {
  if (count <= 1) {
    return { cols: 1, rows: 1 };
  }
  let cols = Math.max(1, Math.round(Math.sqrt(count * aspect)));
  let rows = Math.max(1, Math.ceil(count / cols));
  while (cols > 1 && (cols - 1) * rows >= count) {
    cols -= 1;
  }
  while (rows > 1 && cols * (rows - 1) >= count) {
    rows -= 1;
  }
  if (cols * rows < count) {
    cols = Math.ceil(count / rows);
  }
  return { cols, rows };
};

const clusterRadiusFor = (memberCount: number, hubCount: number) => {
  const local = 160 + Math.min(260, Math.sqrt(Math.max(1, memberCount)) * 52);
  // Fewer hubs → let each constellation breathe across the viewport.
  const hubBoost = hubCount <= 1 ? 1.35 : hubCount <= 4 ? 1.15 : 1;
  return local * hubBoost;
};

const shellEllipse = (shell: number, shellCount: number, clusterR: number) => {
  const t = shell / 4;
  const grow = 1 + Math.min(0.5, Math.max(0, shellCount - 1) * 0.045);
  const rx = clusterR * (0.3 + t * 0.7) * grow;
  const rz = rx * 0.76;
  return { rx, rz };
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
  if (hubs.has(startId)) {
    return startId;
  }
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
      if (hubs.has(next)) {
        return next;
      }
      seen.add(next);
      queue.push(next);
    }
  }
  return null;
};

const LineageUniverseScene = ({ nodes, edges, selectedAssetId, mode, onSelect }: Props) => {
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

    const members = new Map<string, string[]>();
    for (const hub of hubList) {
      members.set(hub, []);
    }
    const orphanIds: string[] = [];
    for (const node of nodes) {
      if (hubIds.has(node.id)) {
        continue;
      }
      const hub = nearestHub(node.id, hubIds, adj);
      if (hub) {
        members.get(hub)?.push(node.id);
      } else {
        orphanIds.push(node.id);
      }
    }

    const maxMembers = Math.max(
      1,
      ...hubList.map((hub) => members.get(hub)?.length ?? 0),
      orphanIds.length
    );
    const clusterR = clusterRadiusFor(maxMembers, Math.max(1, hubList.length));
    const { cols, rows } = hubGridDims(Math.max(1, hubList.length));
    const gapX = clusterR * 2.7;
    const gapZ = clusterR * 2.15;
    const originX = -((cols - 1) * gapX) / 2;
    const originZ = -((rows - 1) * gapZ) / 2;
    const hubPos = new Map<string, { x: number; z: number; clusterR: number }>();
    hubList.forEach((id, index) => {
      const col = index % cols;
      const row = Math.floor(index / cols);
      const localMembers = members.get(id)?.length ?? 0;
      hubPos.set(id, {
        x: originX + col * gapX,
        z: originZ + row * gapZ,
        clusterR: clusterRadiusFor(localMembers, hubList.length),
      });
    });

    const bodies: Body[] = [];
    const placeAt = (
      node: LineageNode,
      shell: number,
      hubId: string | null,
      x: number,
      y: number,
      z: number
    ) => {
      const size =
        shell === 0 ? 22 : shell === 1 ? 16 : shell === 4 ? 14 : node.asset_type === 'PROCESS' ? 15 : 13;
      bodies.push({
        id: node.id,
        label: node.display_name,
        type: node.asset_type,
        color: node.unresolved ? '#ff4d4f' : TYPE_ACCENT[node.asset_type] || '#8c8c8c',
        unresolved: node.unresolved,
        hubId,
        shell,
        x,
        y,
        z,
        homeX: x,
        homeY: y,
        homeZ: z,
        vx: 0,
        vy: 0,
        vz: 0,
        r: node.id === selectedAssetId ? size + 4 : size,
      });
    };

    hubList.forEach((id) => {
      const node = byId.get(id);
      const pos = hubPos.get(id);
      if (!node || !pos) {
        return;
      }
      placeAt(node, 0, id, pos.x, 0, pos.z);
    });

    for (const hub of hubList) {
      const pos = hubPos.get(hub);
      if (!pos) {
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
        const { rx, rz } = shellEllipse(shell, list.length, pos.clusterR);
        list.forEach((node, index) => {
          const angle =
            (index / Math.max(list.length, 1)) * Math.PI * 2 + shell * 0.4 - Math.PI / 2;
          const x = pos.x + Math.cos(angle) * rx;
          const z = pos.z + Math.sin(angle) * rz;
          const y = (shell - 2) * 22 + (index % 3) * 12 - 12;
          placeAt(node, shell, hub, x, y, z);
        });
      }
    }

    if (orphanIds.length) {
      const orphanCols = Math.max(1, Math.ceil(Math.sqrt(orphanIds.length * 1.5)));
      const orphanRows = Math.max(1, Math.ceil(orphanIds.length / orphanCols));
      const orphanGap = clusterR * 0.85;
      const fieldBottom =
        hubList.length > 0 ? originZ + (rows - 1) * gapZ + clusterR * 1.35 : 0;
      const orphanOriginX = -((orphanCols - 1) * orphanGap) / 2;
      const orphanOriginZ = hubList.length > 0 ? fieldBottom : -((orphanRows - 1) * orphanGap) / 2;
      orphanIds.forEach((id, index) => {
        const node = byId.get(id);
        if (!node) {
          return;
        }
        const col = index % orphanCols;
        const row = Math.floor(index / orphanCols);
        placeAt(
          node,
          shellForType(node.asset_type),
          null,
          orphanOriginX + col * orphanGap,
          0,
          orphanOriginZ + row * orphanGap
        );
      });
    }

    // Bridge hint: shared TABLE/VIEW sits between its hubs on the rectangular field.
    for (const body of bodies) {
      if (body.shell < 4 || !body.hubId) {
        continue;
      }
      const neighbours = new Set<string>();
      for (const next of adj.get(body.id) ?? []) {
        const hub = nearestHub(next, hubIds, adj);
        if (hub) {
          neighbours.add(hub);
        }
      }
      if (neighbours.size < 2) {
        continue;
      }
      const hubsAround = [...neighbours];
      let x = 0;
      let z = 0;
      let counted = 0;
      for (const hub of hubsAround) {
        const pos = hubPos.get(hub);
        if (!pos) {
          continue;
        }
        x += pos.x;
        z += pos.z;
        counted += 1;
      }
      if (!counted) {
        continue;
      }
      body.homeX = x / counted;
      body.homeZ = z / counted;
      body.homeY = 40;
      body.x = body.homeX;
      body.y = body.homeY;
      body.z = body.homeZ;
      body.r += 3;
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
    // Flatter overview angle suits a rectangular field.
    let yaw = -0.18;
    let pitch = 0.58;
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
    let velYaw = 0.00018;
    let velPitch = 0;
    let hoverId: string | null = null;
    let focusId = selectedAssetId ?? hubList[0] ?? bodies[0]?.id ?? null;
    let pulse = 0;
    let raf = 0;
    let hits: ScreenHit[] = [];
    let userAdjustedView = false;
    let followFocus = false;
    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    const fitScene = (snap = false) => {
      if (!width || !height || !bodies.length) {
        return;
      }
      followFocus = false;
      const cx = (fieldBounds.minX + fieldBounds.maxX) / 2;
      const cy = (fieldBounds.minY + fieldBounds.maxY) / 2;
      const cz = (fieldBounds.minZ + fieldBounds.maxZ) / 2;
      targetLookX = cx;
      targetLookY = cy;
      targetLookZ = cz;
      panX = 0;
      panY = 0;
      const spanX = Math.max(320, fieldBounds.maxX - fieldBounds.minX);
      const spanZ = Math.max(260, fieldBounds.maxZ - fieldBounds.minZ);
      const spanY = Math.max(80, fieldBounds.maxY - fieldBounds.minY);
      // Perspective foreshortening: Z contributes less on screen at this pitch.
      const worldSpan = Math.max(spanX * 0.58, spanZ * 0.5, spanY * 0.35);
      const viewSpan = Math.min(width, height) * 0.78;
      targetZoom = Math.max(0.42, Math.min(2.35, viewSpan / worldSpan));
      if (snap) {
        lookX = cx;
        lookY = cy;
        lookZ = cz;
        zoom = targetZoom;
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
        fitScene(true);
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
      ctx.fillStyle = emphasis ? 'rgba(15, 23, 42, 0.92)' : 'rgba(8, 12, 24, 0.82)';
      ctx.strokeStyle = emphasis ? 'rgba(125, 211, 252, 0.55)' : 'rgba(255,255,255,0.14)';
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
      ctx.fillStyle = '#f8fbff';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText(text, x, top + boxH / 2);
    };

    const drawFrame = () => {
      pulse += reduced ? 0 : 0.03;
      zoom += (targetZoom - zoom) * 0.08;
      const lookEase = reduced ? 1 : 0.08;
      lookX += (targetLookX - lookX) * lookEase;
      lookY += (targetLookY - lookY) * lookEase;
      lookZ += (targetLookZ - lookZ) * lookEase;
      // Soft-follow only after an explicit fly-to (not the default overview).
      if (followFocus && focusId) {
        const focused = bodyMap.get(focusId);
        if (focused) {
          targetLookX += (focused.x - targetLookX) * 0.12;
          targetLookY += (focused.y - targetLookY) * 0.12;
          targetLookZ += (focused.z - targetLookZ) * 0.12;
        }
      }
      // Idle spin stays slow; pause while hovering so a click is easy to land.
      if (!dragMode && !reduced && !hoverId) {
        yaw += velYaw;
        pitch += velPitch;
        velYaw *= 0.985;
        velPitch *= 0.985;
        if (Math.abs(velYaw) < 0.00016) {
          velYaw = 0.00016;
        }
      }
      if (!reduced) {
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

      // Rectangular field frame + local ellipses around each DATA_SOURCE.
      ctx.save();
      const frame = [
        project(fieldBounds.minX, 0, fieldBounds.minZ),
        project(fieldBounds.maxX, 0, fieldBounds.minZ),
        project(fieldBounds.maxX, 0, fieldBounds.maxZ),
        project(fieldBounds.minX, 0, fieldBounds.maxZ),
      ];
      ctx.beginPath();
      frame.forEach((point, index) => {
        if (index === 0) {
          ctx.moveTo(point.x, point.y);
        } else {
          ctx.lineTo(point.x, point.y);
        }
      });
      ctx.closePath();
      ctx.strokeStyle = 'rgba(125, 211, 252, 0.16)';
      ctx.lineWidth = 1.2;
      ctx.setLineDash([6, 10]);
      ctx.stroke();

      for (const [hubId, pos] of hubPos) {
        const samples = 48;
        const { rx, rz } = shellEllipse(4, members.get(hubId)?.length ?? 1, pos.clusterR);
        ctx.beginPath();
        for (let i = 0; i <= samples; i += 1) {
          const angle = (i / samples) * Math.PI * 2;
          const p = project(pos.x + Math.cos(angle) * rx, 18, pos.z + Math.sin(angle) * rz);
          if (i === 0) {
            ctx.moveTo(p.x, p.y);
          } else {
            ctx.lineTo(p.x, p.y);
          }
        }
        ctx.strokeStyle = 'rgba(134, 239, 172, 0.12)';
        ctx.lineWidth = 1;
        ctx.setLineDash([4, 10]);
        ctx.stroke();
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
        ctx.globalAlpha = hot ? 0.95 : 0.55;
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

        drawLabel(body.label, p.x, p.y + radius + 10, active);
        ctx.font = '10px "Segoe UI", system-ui, sans-serif';
        ctx.fillStyle = active ? 'rgba(186, 210, 255, 0.95)' : 'rgba(186, 210, 255, 0.65)';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'top';
        ctx.fillText(body.type, p.x, p.y + radius + 36);
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

      const tip = hoverId ? byId.get(hoverId) : focusId ? byId.get(focusId) : null;
      if (tip) {
        overlay.dataset.visible = '1';
        const action =
          mode === 'roots'
            ? 'Кликните, чтобы раскрыть цепочку вокруг источника'
            : 'Кликните, чтобы открыть карточку объекта';
        overlay.innerHTML = `<strong>${tip.display_name}</strong><span>${tip.asset_type}</span><em>${tip.qualified_name || tip.id}</em><small>${action}</small>`;
      } else {
        overlay.dataset.visible = '0';
      }

      raf = requestAnimationFrame(drawFrame);
    };

    const resetView = () => {
      focusId = selectedAssetId ?? hubList[0] ?? bodies[0]?.id ?? null;
      userAdjustedView = false;
      yaw = -0.18;
      pitch = 0.58;
      velYaw = 0.00016;
      velPitch = 0;
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
      if (moved) {
        return;
      }
      const rect = canvas.getBoundingClientRect();
      const id = hitTest(event.clientX - rect.left, event.clientY - rect.top);
      if (!id) {
        return;
      }
      focusId = id;
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
  }, [nodes, edges, selectedAssetId, mode, onSelect]);

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
