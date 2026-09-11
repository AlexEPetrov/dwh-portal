from __future__ import annotations

from domains.catalog.collectors.catalog import CatalogCollector
from domains.catalog.collectors.changes import ChangeCollector
from domains.catalog.collectors.extraction_registry import ExtractionRegistryCollector
from domains.catalog.collectors.storage import StorageCollector
from domains.catalog.providers.extraction_registry import ExtractionRegistryProvider
from domains.catalog.providers.lineage import LineageProvider
from domains.catalog.providers.metadata import MetadataProvider
from domains.catalog.providers.postgres import DirectPostgresMetadataProvider
from domains.catalog.repositories.ports import PortalStore
from settings.portal import DwhCollectorSettings


def run_daily_collection(
    store: PortalStore,
    *,
    metadata_provider: MetadataProvider | None = None,
    lineage_provider: LineageProvider | None = None,
    settings: DwhCollectorSettings | None = None,
) -> dict:
    """Idempotent daily collection sequence used by Airflow or local runs."""
    settings = settings or DwhCollectorSettings()
    metadata_provider = metadata_provider or DirectPostgresMetadataProvider(settings)
    lineage_provider = lineage_provider or ExtractionRegistryProvider(settings)
    catalog_run = CatalogCollector(store, metadata_provider, settings).run()
    storage_run = StorageCollector(store, metadata_provider).run()
    lineage_run = ExtractionRegistryCollector(store, lineage_provider, settings).run()
    change_run = ChangeCollector(store).run()
    return {
        "catalog": catalog_run,
        "storage": storage_run,
        "extraction_registry": lineage_run,
        "changes": change_run,
    }
