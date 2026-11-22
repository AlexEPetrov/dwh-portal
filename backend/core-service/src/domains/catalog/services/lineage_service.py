from __future__ import annotations

import uuid
from collections import deque

from domains.catalog.models import (
    LINEAGE_RELATIONSHIP_TYPES,
    Asset,
    AssetQuery,
    AssetStatus,
    AssetType,
    Relationship,
    RelationshipType,
)
from domains.catalog.repositories.ports import PortalStore

_LIST_PAGE_SIZE = 200


class LineageService:
    """Bounded upstream/downstream traversal over data-flow edges only."""

    def __init__(self, store: PortalStore, max_depth: int = 8):
        self._store = store
        self._max_depth = max_depth

    def list_roots(self) -> dict:
        """Return lineage roots: every DATA_SOURCE and orphan EXTRACTION_SOURCE."""
        index = self._lineage_index()
        assets = self._assets_for(index)
        sources = self._list_active(AssetType.DATA_SOURCE)
        extractions = [
            asset
            for asset in self._list_active(AssetType.EXTRACTION_SOURCE)
            if not self._has_data_source_parent(asset, index, assets)
        ]
        nodes = sources + extractions
        nodes.sort(
            key=lambda asset: (asset.asset_type.value, asset.name.lower(), asset.qualified_name)
        )
        # Bounded downstream tallies for Universe sizing / HUD (edges stay empty).
        counts = {
            asset.id: self._downstream_type_counts(asset.id, index, assets) for asset in nodes
        }
        return {
            "nodes": nodes,
            "edges": [],
            "unresolved_targets": [],
            "counts": counts,
        }

    def _downstream_type_counts(
        self,
        start_id: uuid.UUID,
        index: dict[uuid.UUID, list[Relationship]],
        assets: dict[uuid.UUID, Asset],
        *,
        max_depth: int = 4,
    ) -> dict[str, int]:
        """Count reachable assets by type, excluding the start node itself."""
        counts: dict[str, int] = {}
        queue: deque[tuple[uuid.UUID, int]] = deque([(start_id, 0)])
        seen = {start_id}
        while queue:
            current_id, depth = queue.popleft()
            if depth >= max_depth:
                continue
            for edge in index.get(current_id, []):
                neighbour = (
                    edge.to_asset_id if edge.from_asset_id == current_id else edge.from_asset_id
                )
                if neighbour in seen:
                    continue
                seen.add(neighbour)
                asset = assets.get(neighbour)
                if asset is None or asset.deleted_at is not None:
                    continue
                key = asset.asset_type.value
                counts[key] = counts.get(key, 0) + 1
                queue.append((neighbour, depth + 1))
        return counts

    def get_lineage(self, asset_id: uuid.UUID) -> dict:
        origin = self._store.get_asset(asset_id)
        if origin is None:
            return {"asset": None, "nodes": [], "edges": [], "unresolved_targets": []}

        edges = self._walk(asset_id)
        node_ids = {asset_id}
        for edge in edges:
            node_ids.add(edge.from_asset_id)
            node_ids.add(edge.to_asset_id)
        assets = {asset.id: asset for asset in self._store.get_assets(node_ids)}

        nodes: list[Asset] = []
        unresolved_targets = []
        for node_id in node_ids:
            asset = assets.get(node_id)
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

    def _lineage_index(self) -> dict[uuid.UUID, list[Relationship]]:
        """One read of every data-flow edge, indexed by either endpoint."""
        index: dict[uuid.UUID, list[Relationship]] = {}
        for edge in self._store.list_relationships(types=set(LINEAGE_RELATIONSHIP_TYPES)):
            index.setdefault(edge.from_asset_id, []).append(edge)
            if edge.to_asset_id != edge.from_asset_id:
                index.setdefault(edge.to_asset_id, []).append(edge)
        return index

    def _assets_for(self, index: dict[uuid.UUID, list[Relationship]]) -> dict[uuid.UUID, Asset]:
        node_ids: set[uuid.UUID] = set()
        for edges in index.values():
            for edge in edges:
                node_ids.add(edge.from_asset_id)
                node_ids.add(edge.to_asset_id)
        return {asset.id: asset for asset in self._store.get_assets(node_ids)}

    def _walk(self, start_id: uuid.UUID) -> list[Relationship]:
        visited_edges: dict[uuid.UUID, Relationship] = {}
        frontier = {start_id}
        seen_nodes = {start_id}
        types = set(LINEAGE_RELATIONSHIP_TYPES)

        for _ in range(self._max_depth):
            if not frontier:
                break
            edges = self._store.list_relationships(asset_ids=frontier, types=types)
            next_frontier: set[uuid.UUID] = set()
            for edge in edges:
                visited_edges[edge.id] = edge
                next_frontier.update((edge.from_asset_id, edge.to_asset_id))
            frontier = next_frontier - seen_nodes
            seen_nodes.update(frontier)

        return list(visited_edges.values())

    def _list_active(self, asset_type: AssetType) -> list[Asset]:
        items: list[Asset] = []
        page = 1
        while True:
            batch, total = self._store.list_assets(
                AssetQuery(
                    asset_type=asset_type,
                    status=AssetStatus.ACTIVE,
                    page=page,
                    page_size=_LIST_PAGE_SIZE,
                    sort="name",
                )
            )
            items.extend(batch)
            if len(items) >= total or not batch:
                break
            page += 1
        return items

    def _has_data_source_parent(
        self,
        extraction: Asset,
        index: dict[uuid.UUID, list[Relationship]],
        assets: dict[uuid.UUID, Asset],
    ) -> bool:
        for edge in index.get(extraction.id, []):
            if edge.relationship_type != RelationshipType.EXTRACTS_TO:
                continue
            if edge.to_asset_id != extraction.id:
                continue
            parent = assets.get(edge.from_asset_id)
            if (
                parent is not None
                and parent.asset_type == AssetType.DATA_SOURCE
                and parent.deleted_at is None
            ):
                return True
        return False
