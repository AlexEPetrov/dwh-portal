import type { LineageNode } from '@shared/api/generated';

export type SchemaGroup = {
    key: string;
    label: string;
    color: string;
    ids: Set<string>;
};

/** Separate palette namespace: schema tint never replaces an asset's type color. */
export function schemaGroups(nodes: LineageNode[]): SchemaGroup[] {
    const groups = new Map<string, SchemaGroup>();
    for (const node of nodes) {
        if (node.unresolved || !['TABLE', 'VIEW', 'MATERIALIZED_VIEW'].includes(node.asset_type)
            || !node.database?.trim() || !node.schema_name?.trim()) continue;
        // Tuple encoding preserves dots, quotes and case in canonical identifiers.
        const key = JSON.stringify([node.database, node.schema_name]);
        let group = groups.get(key);
        if (!group) {
            let hash = 2166136261;
            for (const char of key) hash = Math.imul(hash ^ char.charCodeAt(0), 16777619) >>> 0;
            group = {
                key, label: `${node.database}.${node.schema_name}`,
                color: `hsl(${hash % 360}, 58%, 72%)`, ids: new Set()
            };
            groups.set(key, group);
        }
        group.ids.add(node.id);
    }
    return [...groups.values()].sort((a, b) => a.key.localeCompare(b.key));
}

type Point = { id: string; homeX: number; homeY: number; homeZ: number };
export type SchemaPatch = { group: SchemaGroup; ids: string[]; radius: number };

/** Bounded world-space cells, not connected components or a schema-wide hull.
 * Even a long dense chain cannot grow a cloud across lanes/stage columns.
 */
export function schemaPatches(groups: SchemaGroup[], points: Point[]): SchemaPatch[] {
    const byId = new Map(points.map((point) => [point.id, point]));
    const patches: SchemaPatch[] = [];
    const cellSize = 140;
    for (const group of groups) {
        const cells = new Map<string, Point[]>();
        for (const id of [...group.ids].sort()) {
            const point = byId.get(id);
            if (!point) continue;
            const cell = [point.homeX, point.homeY, point.homeZ]
                .map((value) => Math.floor(value / cellSize)).join(':');
            const members = cells.get(cell) ?? [];
            members.push(point);
            cells.set(cell, members);
        }
        for (const members of cells.values()) {
            const center = (axis: 'homeX' | 'homeY' | 'homeZ') =>
                members.reduce((sum, point) => sum + point[axis], 0) / members.length;
            const x = center('homeX'), y = center('homeY'), z = center('homeZ');
            const spread = Math.max(...members.map((point) =>
                Math.hypot(point.homeX - x, point.homeY - y, point.homeZ - z)));
            patches.push({ group, ids: members.map((point) => point.id), radius: spread + 48 });
        }
    }
    return patches;
}
