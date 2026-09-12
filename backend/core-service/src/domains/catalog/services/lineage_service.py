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
        sources = self._list_active(AssetType.DATA_SOURCE)
        extractions = [
            asset
            for asset in self._list_active(AssetType.EXTRACTION_SOURCE)
            if not self._has_data_source_parent(asset)
        ]
        nodes = sources + extractions
        nodes.sort(key=lambda asset: (asset.asset_type.value, asset.name.lower(), asset.qualified_name))
        return {
            "nodes": nodes,
            "edges": [],
            "unresolved_targets": [],
        }

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

    def _has_data_source_parent(self, extraction: Asset) -> bool:
        for edge in self._store.list_relationships(
            asset_id=extraction.id, types={RelationshipType.EXTRACTS_TO}
        ):
            if edge.to_asset_id != extraction.id:
                continue
            parent = self._store.get_asset(edge.from_asset_id)
            if (
                parent is not None
                and parent.asset_type == AssetType.DATA_SOURCE
                and parent.deleted_at is None
            ):
                return True
        return False
