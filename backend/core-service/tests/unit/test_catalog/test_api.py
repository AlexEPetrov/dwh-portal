import datetime
import uuid

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.portal import portal_router
from domains.catalog.runtime import (
    get_collection_service,
    get_extraction_load_service,
    reset_portal_store,
)
from domains.catalog.services.collection_service import (
    CollectOptions,
    CollectResult,
    CollectRunSummary,
)


def _client() -> TestClient:
    reset_portal_store()
    app = FastAPI()
    app.include_router(portal_router)
    return TestClient(app)


def test_overview_and_assets_use_canonical_payload():
    client = _client()
    overview = client.get("/api/v1/overview").json()
    assert overview["asset_counts"]["tables"] >= 1
    assert "extract_options" not in overview
    assets = client.get("/api/v1/assets", params={"q": "ice_brent", "type": "TABLE"}).json()
    assert assets["total"] == 1
    item = assets["items"][0]
    assert item["name"] == "ice_brent"
    assert "metrics" in item
    assert "source_files" in item
    detail = client.get(f"/api/v1/assets/{item['id']}").json()
    assert detail["description"]
    assert "source_files" in detail
    columns = client.get(f"/api/v1/assets/{item['id']}/columns").json()
    assert columns["items"][0]["name"] == "trade_date"
    lineage = client.get(f"/api/v1/assets/{item['id']}/lineage").json()
    assert lineage["nodes"]
    assert all(edge["relationship_type"] != "CONTAINS" for edge in lineage["edges"])
    roots = client.get("/api/v1/lineage/roots").json()
    assert roots["edges"] == []
    assert any(
        node["name"] == "ICE" and node["asset_type"] == "DATA_SOURCE" for node in roots["nodes"]
    )
    assert all(node["name"] != "Brent Settlement" for node in roots["nodes"])


def test_storage_changes_and_collection_status():
    client = _client()
    storage = client.get("/api/v1/storage").json()
    assert storage["total_bytes"] > 0
    history = client.get("/api/v1/storage/history").json()
    assert history["items"]
    changes = client.get("/api/v1/changes").json()
    assert changes["total"] == 3
    change_id = changes["items"][0]["id"]
    detail = client.get(f"/api/v1/changes/{change_id}").json()
    assert detail["change_type"]
    status = client.get("/api/v1/collection-status").json()
    names = {item["collector_name"] for item in status["items"]}
    assert {"catalog", "storage", "extraction_registry", "changes"} <= names


class _FakeCollectionService:
    def __init__(self, result: CollectResult | None = None):
        self.seen: CollectOptions | None = None
        self._result = result

    def run(self, options: CollectOptions | None = None) -> CollectResult:
        self.seen = options or CollectOptions()
        if self._result is not None:
            return self._result
        mode = self.seen.airflow_lineage_mode or "catalog"
        return CollectResult(
            reset=self.seen.reset,
            airflow_lineage_mode=mode,
            failed=False,
            schemas=list(self.seen.schemas) if self.seen.schemas else None,
            runs={
                "catalog": CollectRunSummary(status="SUCCESS", message="ok", details={}),
            },
        )


def test_collect_endpoint_accepts_query_and_body_flags():
    fake = _FakeCollectionService()
    reset_portal_store()
    app = FastAPI()
    app.include_router(portal_router)
    app.dependency_overrides[get_collection_service] = lambda: fake
    client = TestClient(app)

    query = client.post(
        "/api/v1/collect",
        params={"reset": True, "airflow_lineage_mode": "code"},
    )
    assert query.status_code == 200
    body = query.json()
    assert body["reset"] is True
    assert body["airflow_lineage_mode"] == "code"
    assert body["failed"] is False
    assert fake.seen is not None
    assert fake.seen.reset is True
    assert fake.seen.airflow_lineage_mode == "code"

    json_resp = client.post(
        "/api/v1/collect",
        json={"reset": False, "airflow_lineage_mode": "catalog"},
    )
    assert json_resp.status_code == 200
    assert json_resp.json()["airflow_lineage_mode"] == "catalog"
    assert fake.seen.reset is False
    assert fake.seen.airflow_lineage_mode == "catalog"

    scoped = client.post(
        "/api/v1/collect",
        params=[("schemas", "raw"), ("schemas", "core")],
    )
    assert scoped.status_code == 200
    assert scoped.json()["schemas"] == ["raw", "core"]
    assert fake.seen.schemas == ("raw", "core")

    replaced = client.post(
        "/api/v1/collect",
        params=[("schemas", "raw")],
        json={"schemas": ["raw", "core", "mart"]},
    )
    assert replaced.status_code == 200
    assert replaced.json()["schemas"] == ["raw", "core", "mart"]
    assert fake.seen.schemas == ("raw", "core", "mart")


def test_collect_endpoint_returns_500_when_a_collector_failed():
    fake = _FakeCollectionService(
        CollectResult(
            reset=False,
            airflow_lineage_mode="catalog",
            failed=True,
            runs={
                "catalog": CollectRunSummary(
                    status="FAILED", message="boom", details={"error": "boom"}
                )
            },
        )
    )
    reset_portal_store()
    app = FastAPI()
    app.include_router(portal_router)
    app.dependency_overrides[get_collection_service] = lambda: fake
    client = TestClient(app)
    response = client.post("/api/v1/collect")
    assert response.status_code == 500
    assert response.json()["failed"] is True
    assert response.json()["runs"]["catalog"]["status"] == "FAILED"


class _FakeLoadService:
    def __init__(self, pages: dict):
        self.pages = pages

    def list_loads(self, asset_id, page: int, page_size: int, *, include_total=True):
        from domains.catalog.providers.log_files import LoadFilePage

        if asset_id not in self.pages:
            return None
        items = self.pages[asset_id]
        start = (page - 1) * page_size
        return LoadFilePage(
            items=items[start : start + page_size],
            total=len(items) if include_total else None,
            available=True,
            has_more=start + page_size < len(items),
        )


def test_asset_loads_are_paged_for_registry_extraction():
    from domains.catalog.providers.log_files import LoadFileRecord

    reset_portal_store()
    extraction_id = uuid.UUID("44444444-4444-4444-4444-444444444402")
    items = [
        LoadFileRecord(
            id="2",
            file_name="new.xlsx",
            loaded_at=datetime.datetime(2026, 1, 3, tzinfo=datetime.timezone.utc),
        ),
        LoadFileRecord(
            id="1",
            file_name="old.xlsx",
            loaded_at=datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc),
        ),
    ]
    app = FastAPI()
    app.include_router(portal_router)
    app.dependency_overrides[get_extraction_load_service] = lambda: _FakeLoadService(
        {extraction_id: items}
    )
    client = TestClient(app)

    response = client.get(
        f"/api/v1/assets/{extraction_id}/loads", params={"page": 1, "page_size": 1}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["available"] is True
    assert body["total"] == 2
    assert body["page_size"] == 1
    assert body["items"][0]["file_name"] == "new.xlsx"
    assert body["has_more"] is True

    fast = client.get(
        f"/api/v1/assets/{extraction_id}/loads",
        params={"page": 1, "page_size": 1, "include_total": False},
    )
    assert fast.status_code == 200
    assert fast.json()["total"] is None
    assert fast.json()["has_more"] is True
    assert len(fast.json()["items"]) == 1
    last = client.get(
        f"/api/v1/assets/{extraction_id}/loads",
        params={"page": 2, "page_size": 1, "include_total": False},
    )
    assert last.json()["has_more"] is False
    assert last.json()["items"][0]["file_name"] == "old.xlsx"

    missing = client.get(f"/api/v1/assets/{uuid.uuid4()}/loads")
    assert missing.status_code == 404


def test_demo_table_loads_are_unavailable_without_dwh_query():
    client = _client()
    assets = client.get("/api/v1/assets", params={"q": "ice_brent", "type": "TABLE"}).json()
    table_id = assets["items"][0]["id"]
    body = client.get(f"/api/v1/assets/{table_id}/loads").json()
    assert body["available"] is False
    assert body["items"] == []
    assert body["total"] == 0
