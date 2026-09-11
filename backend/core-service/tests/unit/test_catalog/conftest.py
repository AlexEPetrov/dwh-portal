import datetime

import pytest

from domains.catalog.repositories.memory import InMemoryPortalStore
from domains.catalog.runtime import reset_portal_store
from domains.catalog.seed import seed_demo_catalog


@pytest.fixture
def store() -> InMemoryPortalStore:
    return InMemoryPortalStore()


@pytest.fixture
def seeded_store(store: InMemoryPortalStore) -> InMemoryPortalStore:
    seed_demo_catalog(store)
    return store


@pytest.fixture
def now() -> datetime.datetime:
    return datetime.datetime(2026, 9, 6, 2, 15, tzinfo=datetime.timezone.utc)


@pytest.fixture(autouse=True)
def _reset_runtime():
    reset_portal_store()
    yield
    reset_portal_store()
