import datetime
import uuid

from domains.catalog.models import Asset, AssetType
from domains.catalog.repositories.memory import InMemoryPortalStore
from domains.catalog.repositories.sql import SqlPortalStore
from domains.catalog.runtime import create_portal_store, reset_portal_store
from settings.portal import PortalSettings


def test_create_portal_store_memory_seeds_by_default():
    reset_portal_store()
    store = create_portal_store(PortalSettings(store="memory", seed_demo=True))
    assert isinstance(store, InMemoryPortalStore)
    assert not store.is_empty()


def test_create_portal_store_sql_never_seeds(monkeypatch):
    reset_portal_store()
    created: list[SqlPortalStore] = []

    class FakeSqlStore(SqlPortalStore):
        def __init__(self) -> None:
            # Avoid opening a real DB session in unit tests.
            super().__init__(session_factory=lambda: (_ for _ in ()).throw(RuntimeError("no db")))
            created.append(self)

        def is_empty(self) -> bool:
            return True

    monkeypatch.setattr("domains.catalog.runtime.SqlPortalStore", FakeSqlStore)
    store = create_portal_store(PortalSettings(store="sql", seed_demo=True))
    assert isinstance(store, FakeSqlStore)
    assert len(created) == 1
    assert store.is_empty()


def test_sql_asset_mapping_round_trip_helpers():
    now = datetime.datetime(2026, 9, 6, tzinfo=datetime.timezone.utc)
    asset = Asset(
        id=uuid.uuid4(),
        asset_type=AssetType.TABLE,
        qualified_name="dwh.raw.ice_brent",
        name="ice_brent",
        description="demo",
        source_provider="postgres",
        native_id="123",
        identity_key="pg:dwh:raw.ice_brent",
        first_seen_at=now,
        last_seen_at=now,
        attributes={"database": "dwh", "schema": "raw"},
    )
    # Build a lightweight stand-in row object with the same attributes as ORM.
    row = type("Row", (), asset.model_dump())()
    row.asset_type = asset.asset_type.value
    mapped = SqlPortalStore._asset_from_row(row)  # type: ignore[arg-type]
    assert mapped.id == asset.id
    assert mapped.asset_type == AssetType.TABLE
    assert mapped.attributes["schema"] == "raw"
