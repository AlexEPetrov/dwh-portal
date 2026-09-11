from __future__ import annotations

import uuid
from collections import deque

from domains.catalog.models import LINEAGE_RELATIONSHIP_TYPES, Asset, Relationship
from domains.catalog.repositories.ports import PortalStore


class LineageService:
    """Bounded upstream/downstream traversal over data-flow edges only."""

    def __init__(self, store: PortalStore, max_depth: int = 8):
        self._store = store
        self._max_depth = max_depth

    def get_lineage(self, asset_id: uuid.UUID) -> dict:
        origin = self._store.get_asset(asset_id)
        if origin is None:
            return {"asset": None, "nodes": [], "edges": [], "unresolved_targets": []}

        edges = self._walk(asset_id)
        node_ids = {asset_id}
        for edge in edges:
            node_ids.add(edge.from_asset_id)
            node_ids.add(edge.to_asset_id)

        nodes: list[Asset] = []
        unresolved_targets = []
        for node_id in node_ids:
            asset = self._store.get_asset(node_id)
            if asset is None:
                continue
            nodes.append(asset)
            if asset.attributes.get("unresolved"):
                unresolved_targets.append(
                    {
                        "asset_id": str(asset.id),
                        "qualified_name": asset.qualified_name,
                        "target_ref": asset.attributes.get("target_ref", {}),
                    }
                )

        return {
            "asset": origin,
            "nodes": nodes,
            "edges": edges,
            "unresolved_targets": unresolved_targets,
        }

    def _walk(self, start_id: uuid.UUID) -> list[Relationship]:
        visited_edges: dict[uuid.UUID, Relationship] = {}
        queue: deque[tuple[uuid.UUID, int]] = deque([(start_id, 0)])
        seen_nodes = {start_id}

        while queue:
            current_id, depth = queue.popleft()
            if depth >= self._max_depth:
                continue
            for edge in self._store.list_relationships(
                asset_id=current_id, types=set(LINEAGE_RELATIONSHIP_TYPES)
            ):
                visited_edges[edge.id] = edge
                neighbour = edge.to_asset_id if edge.from_asset_id == current_id else edge.from_asset_id
                if neighbour not in seen_nodes:
                    seen_nodes.add(neighbour)
                    queue.append((neighbour, depth + 1))
        return list(visited_edges.values())
