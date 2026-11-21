"""Exercise the actual SDK HTTP transport with memory snapshots, never a live DB."""

import asyncio
import importlib
import json
import uuid
from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi.testclient import TestClient

from api import catalog_mcp
from domains.catalog.models import AssetColumn
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
            "universe": f"/lineage/universe/{asset_id}",
        }
        assert detail["navigation"] == {
            "portal": f"/objects/{asset_id}",
            "universe": f"/lineage/universe/{asset_id}",
        }
        links = call(client, "get_object_links", {"asset_id": asset_id})["structuredContent"]
        assert links["data"] == detail["data"]["links"]


@pytest.mark.parametrize("description_location", ["object", "column"])
def test_topic_search_finds_description_only_matches_and_equals_rest(description_location):
    from api.host import app

    with TestClient(app) as client:
        store = get_portal_store()
        original_id = client.get("/api/v1/assets").json()["items"][0]["id"]
        original = store.get_asset(uuid.UUID(original_id))
        asset = store.upsert_asset(
            original.model_copy(
                update={
                    "id": uuid.uuid4(),
                    "identity_key": "description-only-topic",
                    "name": "assessments",
                    "qualified_name": "dwh.raw.assessments",
                    "description": "Котировки Аргус" if description_location == "object" else None,
                }
            )
        )
        if description_location == "column":
            store.replace_columns(
                asset.id,
                [
                    AssetColumn(
                        asset_id=asset.id,
                        ordinal=1,
                        name="value",
                        data_type="numeric",
                        description="Цена по данным Аргус",
                    )
                ],
            )
        rest = client.get("/api/v1/assets", params={"q": "АРГУС"}).json()
        result = call(client, "search_catalog", {"q": "АРГУС"})["structuredContent"]
        assert result["data"] == rest
        assert str(asset.id) in {item["id"] for item in rest["items"]}


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


def test_discovery_publishes_described_parameters_and_concrete_output_schemas():
    from api.host import app

    with TestClient(app) as client:
        tools = {tool["name"]: tool for tool in rpc(client, "tools/list").json()["result"]["tools"]}
        for name, tool in tools.items():
            assert len(tool["description"]) > 150
            for parameter in tool["inputSchema"]["properties"].values():
                assert len(parameter["description"]) > 20
            output = tool["outputSchema"]
            assert {"data", "redacted_fields", "navigation"} <= set(output["required"])
            assert "CatalogNavigation" in output["$defs"]
            assert output["properties"]["data"].get("$ref")
            assert "additionalProperties" not in output["properties"]["data"]
            assert output["properties"]["redacted_fields"]["items"]["type"] == "string"
            assert tool["annotations"]["readOnlyHint"] is True
            assert tool["annotations"]["openWorldHint"] is False
        search = tools["search_catalog"]["inputSchema"]
        assert search["properties"]["page"]["minimum"] == 1
        assert search["properties"]["page_size"]["minimum"] == 1
        assert "caps it" in search["properties"]["page_size"]["description"]
        assert (
            "object descriptions and column descriptions"
            in search["properties"]["q"]["description"]
        )
        assert "AssetListResponse" in tools["search_catalog"]["outputSchema"]["$defs"]
        assert "AssetDetailResponse" in tools["get_object"]["outputSchema"]["$defs"]
        assert "ColumnItem" in tools["get_object"]["outputSchema"]["$defs"]
        assert "LineageData" in tools["get_lineage"]["outputSchema"]["$defs"]
        assert "ObjectLinks" in tools["get_object_links"]["outputSchema"]["$defs"]


def test_initialization_describes_model_driven_multilingual_ambiguity_policy():
    from api.host import app

    with TestClient(app) as client:
        instructions = rpc(
            client,
            "initialize",
            {
                "protocolVersion": "2025-11-25",
                "capabilities": {},
                "clientInfo": {"name": "metadata-test", "version": "1"},
            },
        ).json()["result"]["instructions"]
        assert "LLM selects tools" in instructions
        assert "not natural-language interpretation" in instructions
        assert "never choose the first arbitrarily" in instructions
        assert "do not silently translate identifiers" in instructions
        assert "Answer in the user's language" in instructions
        assert "at most 20 data rows" in instructions
        assert "BELOW the table" in instructions
        assert "Открыть на портале" in instructions
        assert "Открыть в Universe" in instructions
        assert "do not fetch every page automatically" in instructions
        assert "q='Аргус'" in instructions
        assert "Search includes object descriptions and column descriptions" in instructions


@pytest.mark.parametrize("base", ["", "https://catalog.example.invalid"])
def test_search_navigation_preserves_filters_without_inventing_a_page_limit(monkeypatch, base):
    from api.host import app

    monkeypatch.setenv("APP_MCP_PUBLIC_BASE_URL", base)
    arguments = {
        "q": "Цена & 東京 / 100% +",
        "database": "dwh/one",
        "schema": "raw+market",
        "asset_types": ["VIEW", "MATERIALIZED_VIEW"],
        "source": "postgres_sql",
        "status": "deleted",
        "changed_since": "2026-11-21T10:00:00+03:00",
        "page": 3,
        "page_size": 7,
    }
    with TestClient(app) as client:
        payload = call(client, "search_catalog", arguments)["structuredContent"]
        navigation = payload["navigation"]
        url = urlsplit(navigation["portal"])
        assert url.path == "/objects"
        assert url.netloc == ("catalog.example.invalid" if base else "")
        assert parse_qs(url.query) == {
            "q": [arguments["q"]],
            "database": [arguments["database"]],
            "schema": [arguments["schema"]],
            "type": ["VIEW,MATERIALIZED_VIEW"],
            "source": ["postgres_sql"],
            "status": ["deleted"],
            "changed_since": [arguments["changed_since"]],
            "sort": ["qualified_name"],
        }
        assert navigation["universe"] == f"{base}/lineage/universe"
        assert payload["data"]["page_size"] == 7
        assert "page" not in parse_qs(url.query)


def test_twenty_row_display_guidance_does_not_truncate_canonical_tool_data():
    from api.host import app

    with TestClient(app) as client:
        store = get_portal_store()
        asset_id = client.get("/api/v1/assets").json()["items"][0]["id"]
        original = store.get_asset(uuid.UUID(asset_id))
        for index in range(25):
            store.upsert_asset(
                original.model_copy(
                    update={
                        "id": uuid.uuid4(),
                        "identity_key": f"display-limit-{index}",
                        "name": f"preview_many_{index}",
                        "qualified_name": f"raw.preview_many_{index}",
                    }
                )
            )
        result = call(client, "search_catalog", {"q": "preview_many", "page_size": 50})[
            "structuredContent"
        ]
        assert result["data"]["total"] == 25
        assert len(result["data"]["items"]) == 25
        assert (
            result["data"]
            == client.get("/api/v1/assets", params={"q": "preview_many", "page_size": 50}).json()
        )


def test_all_successful_results_validate_against_typed_envelopes():
    from api.host import app
    from api.portal.dto import AssetListResponse

    models = {
        "get_object": catalog_mcp.CatalogResult[catalog_mcp.ObjectData],
        "get_lineage": catalog_mcp.CatalogResult[catalog_mcp.LineageData],
        "get_object_links": catalog_mcp.CatalogResult[catalog_mcp.ObjectLinks],
    }
    with TestClient(app) as client:
        search = call(client, "search_catalog", {})["structuredContent"]
        catalog_mcp.CatalogResult[AssetListResponse].model_validate(search)
        asset_id = search["data"]["items"][0]["id"]
        for name, model in models.items():
            result = call(client, name, {"asset_id": asset_id})
            assert not result.get("isError")
            model.model_validate(result["structuredContent"])
            navigation = result["structuredContent"]["navigation"]
            assert navigation["universe"] == f"/lineage/universe/{asset_id}"
            assert navigation["portal"] == (
                f"/lineage/{asset_id}" if name == "get_lineage" else f"/objects/{asset_id}"
            )


def test_unicode_search_preserves_multiple_matches_without_auto_selecting():
    """Backend preserves candidates; clarification is model policy, not a parser."""
    from api.host import app

    with TestClient(app) as client:
        store = get_portal_store()
        original_id = client.get("/api/v1/assets").json()["items"][0]["id"]
        original = store.get_asset(uuid.UUID(original_id))
        for schema in ("one", "two"):
            store.upsert_asset(
                original.model_copy(
                    update={
                        "id": uuid.uuid4(),
                        "identity_key": f"mcp-multilingual-{schema}",
                        "name": "Продажи_東京",
                        "qualified_name": f"{schema}.Продажи_東京",
                        "attributes": {"schema": schema},
                    }
                )
            )
        result = call(client, "search_catalog", {"q": "Продажи_東京"})["structuredContent"]["data"]
        assert result["total"] == 2
        assert {item["qualified_name"] for item in result["items"]} == {
            "one.Продажи_東京",
            "two.Продажи_東京",
        }


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
        asset.attributes["extract_options"] = {"nested": ["not-for-model"]}
        asset.attributes["metadata"] = [{"credentials": {"token": "not-for-model"}, "count": 3}]
        store.upsert_asset(asset)
        payload = call(client, "get_object", {"asset_id": asset_id})["structuredContent"]
        assert payload["data"]["object"]["attributes"]["provider"] == {
            "password": "[REDACTED]",
            "label": "retained",
        }
        assert "object.attributes.provider.password" in payload["redacted_fields"]
        assert payload["data"]["object"]["attributes"]["extract_options"] == "[REDACTED]"
        assert payload["data"]["object"]["attributes"]["metadata"] == [
            {"credentials": "[REDACTED]", "count": 3}
        ]
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


def test_output_validation_errors_are_sanitized_not_successful_null(monkeypatch):
    from api.host import app

    monkeypatch.setattr(
        catalog_mcp.assets,
        "list_assets",
        lambda **_: {
            "items": [{"id": "private-invalid-output"}],
        },
    )
    with TestClient(app) as client:
        result = call(client, "search_catalog", {})
        assert result["isError"] is True
        assert "structuredContent" not in result
        assert "private-invalid-output" not in json.dumps(result)
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
