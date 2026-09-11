from __future__ import annotations

from typing import Any

from domains.catalog.collectors.extraction_registry import ExtractionRegistryCollector
from domains.catalog.models import CollectionRun
from domains.catalog.providers.extraction_registry import ExtractionRegistryProvider
from domains.catalog.providers.lineage import LineageProvider
from domains.catalog.repositories.ports import PortalStore
from settings.portal import DwhCollectorSettings


class ExtractionRegistryLineageAdapter:
    """Optional source-to-DWH lineage from sys.data_extraction_sources."""

    name = "extraction_registry"

    def __init__(
        self,
        store: PortalStore,
        settings: DwhCollectorSettings | None = None,
        *,
        lineage_provider: LineageProvider | None = None,
        **_kwargs: Any,
    ):
        self._store = store
        self._settings = settings or DwhCollectorSettings()
        self._provider = lineage_provider or ExtractionRegistryProvider(self._settings)

    def collect(self, now: datetime.datetime | None = None) -> CollectionRun:
        return ExtractionRegistryCollector(
            self._store, self._provider, self._settings
        ).run(now)
