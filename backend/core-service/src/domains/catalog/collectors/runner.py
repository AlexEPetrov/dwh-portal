from __future__ import annotations

from domains.catalog.collectors.catalog import CatalogCollector
from domains.catalog.collectors.changes import ChangeCollector
from domains.catalog.collectors.storage import StorageCollector
from domains.catalog.lineage_adapters.protocol import LineageAdapter
from domains.catalog.lineage_adapters.registry import load_lineage_adapters
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
    lineage_adapters: list[LineageAdapter] | None = None,
    settings: DwhCollectorSettings | None = None,
    schemas: tuple[str, ...] | None = None,
) -> dict:
    """Idempotent daily collection sequence used by Airflow or local runs.

    ``schemas`` limits PostgreSQL catalog reads to that allow-list. The list
    is the full active catalog scope for the run: grow it across calls.
    Omitting a previously collected schema soft-deletes it.
    """
    settings = settings or DwhCollectorSettings()
    metadata_provider = metadata_provider or DirectPostgresMetadataProvider(
        settings, schemas=schemas
    )
    catalog_run = CatalogCollector(store, metadata_provider, settings).run()
    storage_run = StorageCollector(store).run()
    adapters = lineage_adapters or load_lineage_adapters(
        store,
        settings,
        lineage_provider=lineage_provider,
        metadata_provider=metadata_provider,
    )
    lineage_runs = {adapter.name: adapter.collect() for adapter in adapters}
    change_run = ChangeCollector(store).run()
    return {
        "catalog": catalog_run,
        "storage": storage_run,
        **lineage_runs,
        "changes": change_run,
    }
