from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.portal import portal_router
from domains.catalog.runtime import reset_portal_store


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
