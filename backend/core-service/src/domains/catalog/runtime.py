from __future__ import annotations

from functools import lru_cache

from domains.catalog.repositories.memory import InMemoryPortalStore
from domains.catalog.repositories.ports import PortalStore
from domains.catalog.repositories.sql import SqlPortalStore
from domains.catalog.seed import seed_demo_catalog
from domains.catalog.services.asset_service import AssetService
from domains.catalog.services.change_service import ChangeService
from domains.catalog.services.collection_service import CollectionService
from domains.catalog.services.collection_status_service import CollectionStatusService
from domains.catalog.services.extraction_load_service import ExtractionLoadService
from domains.catalog.services.lineage_service import LineageService
from domains.catalog.services.overview_service import OverviewService
from domains.catalog.services.storage_service import StorageService
from settings.portal import PortalSettings

_store: PortalStore | None = None


def reset_portal_store() -> None:
    """Test helper that drops the process-local snapshot store."""
    global _store
    _store = None
    get_portal_settings.cache_clear()


@lru_cache
def get_portal_settings() -> PortalSettings:
    return PortalSettings()


def create_portal_store(settings: PortalSettings | None = None) -> PortalStore:
    """Build a PortalStore for the given settings (or current env)."""
    settings = settings or get_portal_settings()
    if settings.store == "sql":
        return SqlPortalStore()
    store: PortalStore = InMemoryPortalStore()
    if settings.seed_demo:
        seed_demo_catalog(store)
    return store


def get_portal_store() -> PortalStore:
    global _store
    if _store is None:
        _store = create_portal_store()
    return _store


def get_asset_service() -> AssetService:
    return AssetService(get_portal_store())


def get_storage_service() -> StorageService:
    return StorageService(get_portal_store())


def get_lineage_service() -> LineageService:
    return LineageService(get_portal_store(), max_depth=get_portal_settings().lineage_max_depth)


def get_extraction_load_service() -> ExtractionLoadService:
    return ExtractionLoadService(get_portal_store())


def get_change_service() -> ChangeService:
    return ChangeService(get_portal_store())


def get_overview_service() -> OverviewService:
    return OverviewService(get_portal_store(), stale_after_hours=get_portal_settings().stale_after_hours)


def get_collection_status_service() -> CollectionStatusService:
    return CollectionStatusService(
        get_portal_store(), stale_after_hours=get_portal_settings().stale_after_hours
    )


def get_collection_service() -> CollectionService:
    return CollectionService(get_portal_store(), get_portal_settings())
