from __future__ import annotations

import datetime
import uuid

from domains.catalog.models import Asset, AssetColumn, AssetListEntry, AssetQuery, ChangeQuery
from domains.catalog.repositories.ports import PortalStore


class AssetService:
    """Read canonical assets from Portal snapshots."""

    def __init__(self, store: PortalStore):
        self._store = store

    def list_assets(self, query: AssetQuery) -> tuple[list[Asset], int]:
        return self._store.list_assets(query)

    def list_page(self, query: AssetQuery) -> tuple[list[AssetListEntry], int]:
        """Return one grid page with its latest size snapshot and change time.

        Callers that need the asset alone keep using ``list_assets``. The list
        screen uses this so size and change time are not loaded per row.
        """
        return self._store.list_asset_page(query)

    def get_asset(self, asset_id: uuid.UUID) -> Asset | None:
        return self._store.get_asset(asset_id)

    def get_columns(self, asset_id: uuid.UUID) -> list[AssetColumn]:
        return self._store.get_columns(asset_id)

    def latest_change_at(self, asset_id: uuid.UUID) -> datetime.datetime | None:
        events, _ = self._store.list_changes(ChangeQuery(asset_id=asset_id, page=1, page_size=1))
        return events[0].detected_at if events else None
