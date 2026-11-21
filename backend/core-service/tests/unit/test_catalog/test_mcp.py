"""Exercise the actual SDK HTTP transport with memory snapshots, never a live DB."""

import asyncio
import importlib
import json
import uuid

import pytest
from fastapi.testclient import TestClient

from api import catalog_mcp
from domains.catalog.runtime import get_portal_store
from settings.mcp import CatalogMcpSettings

HEADERS = {
    "Accept": "application/json, text/event-stream",
    "MCP-Protocol-Version": "2025-11-25",
}


@pytest.fixture(autouse=True)
def settings(monkeypatch):
    monkeypatch.setenv("APP_PORTAL_STORE", "memory")
    monkeypatch.setenv("APP_PORTAL_SEED_DEMO", "true")
    monkeypatch.setenv("APP_MCP_ENABLED", "true")
    monkeypatch.setenv("APP_MCP_ALLOW_ANONYMOUS_READ", "true")
    monkeypatch.setenv("APP_MCP_ALLOWED_HOSTS", '["testserver"]')
    monkeypatch.setenv("APP_MCP_ALLOWED_ORIGINS", "[]")
    monkeypatch.setenv("APP_MCP_PUBLIC_BASE_URL", "")
    monkeypatch.delenv("APP_MCP_TOKEN", raising=False)


def rpc(client, method, params=None, headers=None):
    body = {"jsonrpc": "2.0", "id": 1, "method": method}
    if params is not None:
        body["params"] = params
    return client.post("/mcp", json=body, headers={**HEADERS, **(headers or {})})


def call(client, name, arguments):
    response = rpc(client, "tools/call", {"name": name, "arguments": arguments})
    assert response.status_code == 200, response.text
    return response.json()["result"]


@pytest.mark.parametrize("module_name", ["api.host", "api.portal_host"])
def test_both_hosts_initialize_discover_and_shutdown(module_name):
    module = importlib.import_module(module_name)
    with TestClient(module.app) as client:
        response = rpc(
            client,
            "initialize",
            {
                "protocolVersion": "2025-03-26",
                "capabilities": {},
                "clientInfo": {"name": "portal-test", "version": "1"},
            },
        )
        assert response.status_code == 200, response.text
        assert response.json()["result"]["serverInfo"]["name"] == "DWH Portal catalog"
        tools = rpc(client, "tools/list").json()["result"]["tools"]
        assert {tool["name"] for tool in tools} == set(catalog_mcp.TOOL_NAMES)
        assert all(tool["annotations"]["readOnlyHint"] for tool in tools)
        assert all(not tool["annotations"]["destructiveHint"] for tool in tools)
        assert module.catalog_mcp.application is not None
    assert module.catalog_mcp.application is None


def test_search_detail_columns_and_links_equal_rest():
    from api.host import app

    with TestClient(app) as client:
        rest = client.get(
            "/api/v1/assets", params={"q": "ice_brent", "type": "TABLE", "page_size": 50}
        ).json()
        result = call(client, "search_catalog", {"q": "ice_brent", "asset_types": ["TABLE"]})
        assert result.get("isError") is not True
        payload = result["structuredContent"]
        assert payload["data"] == rest
        assert payload["redacted_fields"] == []
        asset_id = rest["items"][0]["id"]
        detail = call(client, "get_object", {"asset_id": asset_id})["structuredContent"]
        assert detail["data"]["object"] == client.get(f"/api/v1/assets/{asset_id}").json()
        assert (
            detail["data"]["columns"]
            == client.get(f"/api/v1/assets/{asset_id}/columns").json()["items"]
        )
        assert detail["data"]["links"] == {
            "object": f"/objects/{asset_id}",
            "lineage": f"/lineage/{asset_id}",
        }
        links = call(client, "get_object_links", {"asset_id": asset_id})["structuredContent"]
        assert links["data"] == detail["data"]["links"]


def test_lineage_preserves_exact_canonical_graph():
    from api.host import app

    with TestClient(app) as client:
        asset_id = client.get("/api/v1/assets", params={"q": "ice_brent"}).json()["items"][0]["id"]
        expected = client.get(f"/api/v1/assets/{asset_id}/lineage").json()
        actual = call(client, "get_lineage", {"asset_id": asset_id})["structuredContent"]["data"]
        for key, value in expected.items():
            assert actual[key] == value
        assert actual["bounded"] is True
        assert actual["evidence"] == "catalog_snapshot_not_execution_history"


@pytest.mark.parametrize("method", ["initialize", "tools/list", "tools/call"])
def test_token_mode_rejects_anonymous_service_keys_and_cookies(monkeypatch, method):
    from api.host import app

    monkeypatch.setenv("APP_MCP_ALLOW_ANONYMOUS_READ", "false")
    monkeypatch.setenv("APP_MCP_TOKEN", "test-mcp-only-credential")
    with TestClient(app) as client:
        for headers in (
            {},
            {"x-api-key": "dev"},
            {"Cookie": "app_session=anything"},
            {"Authorization": "Bearer invalid-secret"},
        ):
            response = rpc(client, method, headers=headers)
            assert response.status_code == 401
            assert "invalid-secret" not in response.text
            assert "test-mcp-only-credential" not in response.text
        response = rpc(
            client, "tools/list", headers={"Authorization": "Bearer test-mcp-only-credential"}
        )
        assert response.status_code == 200, response.text
        assert (
            client.get(
                "/api/auth/session", headers={"Authorization": "Bearer test-mcp-only-credential"}
            ).status_code
            == 401
        )


def test_missing_token_with_anonymous_off_rejects_startup(monkeypatch):
    from api.host import app

    monkeypatch.setenv("APP_MCP_ALLOW_ANONYMOUS_READ", "false")
    with pytest.raises(ValueError, match="requires a token"):
        with TestClient(app):
            pytest.fail("Unconfigured MCP must not accept requests")


def test_disabled_does_not_construct_sdk(monkeypatch):
    from api.host import app

    monkeypatch.setenv("APP_MCP_ENABLED", "false")
    monkeypatch.setattr(catalog_mcp, "create_catalog_server", lambda *_: pytest.fail("SDK started"))
    with TestClient(app) as client:
        assert rpc(client, "tools/list").status_code == 404
        assert client.get("/api/v1/assets").status_code == 200


@pytest.mark.parametrize(
    "headers, expected",
    [
        ({"Host": "attacker.invalid"}, 421),
        ({"Origin": "https://attacker.invalid"}, 403),
    ],
)
def test_transport_rejects_untrusted_host_or_origin(headers, expected):
    from api.host import app

    with TestClient(app) as client:
        assert rpc(client, "tools/list", headers=headers).status_code == expected


@pytest.mark.parametrize("name", ["collect", "execute_sql", "read_file", "get_url", "run_code"])
def test_unknown_tools_cannot_execute(name):
    from api.host import app

    with TestClient(app) as client:
        result = call(client, name, {})
        assert result["isError"] is True


@pytest.mark.parametrize("name", ["get_object", "get_lineage", "get_object_links"])
def test_missing_objects_are_errors(name):
    from api.host import app

    with TestClient(app) as client:
        result = call(client, name, {"asset_id": str(uuid.uuid4())})
        assert result["isError"] is True
        assert "Asset not found" in json.dumps(result)


def test_paging_validation_and_limits():
    from api.host import app
    from domains.catalog.runtime import get_portal_settings

    with TestClient(app) as client:
        assert call(client, "search_catalog", {"page": 0})["isError"] is True
        result = call(client, "search_catalog", {"page_size": 100000})["structuredContent"]
        assert result["data"]["page_size"] == get_portal_settings().max_page_size


def test_nested_secrets_redacted_without_losing_normal_metadata():
    from api.host import app

    with TestClient(app) as client:
        asset_id = client.get("/api/v1/assets").json()["items"][0]["id"]
        store = get_portal_store()
        asset = store.get_asset(uuid.UUID(asset_id))
        asset.attributes["provider"] = {"password": "not-for-model", "label": "retained"}
        store.upsert_asset(asset)
        payload = call(client, "get_object", {"asset_id": asset_id})["structuredContent"]
        assert payload["data"]["object"]["attributes"]["provider"] == {
            "password": "[REDACTED]",
            "label": "retained",
        }
        assert "object.attributes.provider.password" in payload["redacted_fields"]
        assert "not-for-model" not in json.dumps(payload)


def test_backend_exceptions_do_not_leak_connection_details(monkeypatch):
    from api.host import app

    def fail():
        raise RuntimeError("postgres://user:secret@database/private")

    monkeypatch.setattr(catalog_mcp, "get_asset_service", fail)
    with TestClient(app) as client:
        result = call(client, "search_catalog", {})
        assert result["isError"] is True
        assert "secret" not in json.dumps(result)
        assert "Catalog request failed" in json.dumps(result)


@pytest.mark.parametrize(
    "url",
    [
        "https://user:password@example.com",
        "https://example.com?token=secret",
        "file:///tmp/x",
    ],
)
def test_public_link_origin_rejects_credentials_or_arbitrary_schemes(url):
    with pytest.raises(ValueError):
        CatalogMcpSettings(public_base_url=url)


def test_legacy_protocol_keeps_text_catalog_result():
    from api.host import app

    with TestClient(app) as client:
        response = rpc(
            client,
            "tools/call",
            {"name": "search_catalog", "arguments": {"q": "ice_brent"}},
            headers={"MCP-Protocol-Version": "2025-03-26"},
        )
        assert response.status_code == 200
        result = response.json()["result"]
        assert not result.get("isError")
        assert json.loads(result["content"][0]["text"])["data"]["items"]


def test_unresolved_targets_and_stored_direction_are_preserved():
    from api.host import app
    from domains.catalog.models import Relationship, RelationshipType

    with TestClient(app) as client:
        asset_id = client.get("/api/v1/assets").json()["items"][0]["id"]
        store = get_portal_store()
        origin = store.get_asset(uuid.UUID(asset_id))
        target = origin.model_copy(
            update={
                "id": uuid.uuid4(),
                "name": "unresolved_target",
                "qualified_name": "missing.schema.target",
                "identity_key": "mcp-test-unresolved",
                "attributes": {
                    "unresolved": True,
                    "target_ref": {"database": "missing", "name": "target"},
                },
            }
        )
        store.upsert_asset(target)
        edge = Relationship(
            from_asset_id=origin.id,
            to_asset_id=target.id,
            relationship_type=RelationshipType.DERIVED_FROM,
            source_provider="mcp-test",
        )
        store.upsert_relationship(edge)
        data = call(client, "get_lineage", {"asset_id": asset_id})["structuredContent"]["data"]
        assert any(item["asset_id"] == str(target.id) for item in data["unresolved_targets"])
        actual = next(item for item in data["edges"] if item["id"] == str(edge.id))
        assert actual["from_asset_id"] == str(origin.id)
        assert actual["to_asset_id"] == str(target.id)


def test_anonymous_mode_can_be_closed_on_restart(monkeypatch):
    from api.host import app

    with TestClient(app) as client:
        assert rpc(client, "tools/list").status_code == 200
    monkeypatch.setenv("APP_MCP_ALLOW_ANONYMOUS_READ", "false")
    monkeypatch.setenv("APP_MCP_TOKEN", "test-mcp-only-credential")
    with TestClient(app) as client:
        assert rpc(client, "tools/list").status_code == 401


def test_configured_public_origin_and_request_body_limit(monkeypatch):
    from api.host import app

    monkeypatch.setenv("APP_MCP_PUBLIC_BASE_URL", "https://catalog.example.invalid/")
    with TestClient(app) as client:
        asset_id = client.get("/api/v1/assets").json()["items"][0]["id"]
        links = call(client, "get_object_links", {"asset_id": asset_id})["structuredContent"][
            "data"
        ]
        assert links["object"] == f"https://catalog.example.invalid/objects/{asset_id}"
        response = client.post(
            "/mcp",
            content="x" * (1024 * 1024 + 1),
            headers={**HEADERS, "Content-Type": "application/json"},
        )
        assert response.status_code == 413


@pytest.mark.parametrize("anonymous", [True, False])
def test_official_client_negotiates_over_asgi_http(monkeypatch, anonymous):
    import httpx2
    from mcp import Client
    from mcp.client.streamable_http import streamable_http_client

    from api.host import app

    monkeypatch.setenv("APP_MCP_ALLOW_ANONYMOUS_READ", str(anonymous).lower())
    monkeypatch.setenv("APP_MCP_TOKEN", "test-mcp-only-credential")

    async def exercise():
        async with app.router.lifespan_context(app):
            async with httpx2.AsyncClient(
                transport=httpx2.ASGITransport(app=app),
                headers={} if anonymous else {"Authorization": "Bearer test-mcp-only-credential"},
                timeout=httpx2.Timeout(30, read=300),
            ) as http:
                async with Client(
                    streamable_http_client("http://testserver/mcp", http_client=http)
                ) as client:
                    result = await client.call_tool(
                        "search_catalog", {"q": "ice_brent", "asset_types": ["TABLE"]}
                    )
                    assert not result.is_error
                    asset_id = result.structured_content["data"]["items"][0]["id"]
                    detail = await client.call_tool("get_object", {"asset_id": asset_id})
                    assert not detail.is_error
                    assert detail.structured_content["data"]["columns"]

    asyncio.run(exercise())
