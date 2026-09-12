from __future__ import annotations

import uuid

from domains.catalog.models import AssetType
from domains.catalog.providers.log_files import LoadFilePage, LogFilesProvider
from domains.catalog.repositories.ports import PortalStore

REGISTRY_PROVIDER = "extraction_registry"


class ExtractionLoadService:
    """Paged live load log for registry EXTRACTION_SOURCE assets."""

    def __init__(self, store: PortalStore, provider: LogFilesProvider | None = None):
        self._store = store
        self._provider = provider or LogFilesProvider()

    def list_loads(self, asset_id: uuid.UUID, page: int, page_size: int) -> LoadFilePage | None:
        """Return load files for a catalog asset, or None if the asset is missing."""
        asset = self._store.get_asset(asset_id)
        if asset is None:
            return None
        empty = LoadFilePage(items=[], total=0, available=False)
        if asset.asset_type != AssetType.EXTRACTION_SOURCE:
            return empty
        if asset.source_provider != REGISTRY_PROVIDER:
            return empty
        if not asset.native_id:
            return empty
        try:
            uuid.UUID(str(asset.native_id))
        except ValueError:
            return LoadFilePage(items=[], total=0, available=True)
        return self._provider.list_files(str(asset.native_id), page, page_size)
