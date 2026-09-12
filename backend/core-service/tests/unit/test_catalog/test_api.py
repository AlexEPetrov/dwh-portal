from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.portal import portal_router
from domains.catalog.runtime import get_collection_service, reset_portal_store
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
    detail = client.get(f"/api/v1/assets/{item['id']}").json()
    assert detail["description"]
    columns = client.get(f"/api/v1/assets/{item['id']}/columns").json()
    assert columns["items"][0]["name"] == "trade_date"
    lineage = client.get(f"/api/v1/assets/{item['id']}/lineage").json()
    assert lineage["nodes"]
    assert all(edge["relationship_type"] != "CONTAINS" for edge in lineage["edges"])


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
