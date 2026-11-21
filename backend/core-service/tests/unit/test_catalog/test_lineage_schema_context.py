"""Schema context is explicit snapshot evidence, independent of lineage edges."""

import datetime

import pytest

from api.portal.dto import lineage_node
from domains.catalog.models import Asset, AssetType


@pytest.mark.parametrize("asset_type", list(AssetType))
@pytest.mark.parametrize("counts", [None, {"TABLE": 3}])
def test_membership_only_for_resolved_relations(asset_type, counts):
    now = datetime.datetime.now(datetime.UTC)
    asset = Asset(
        asset_type=asset_type,
        qualified_name="misleading.wrong.name",
        name="name",
        source_provider="test",
        identity_key="test",
        first_seen_at=now,
        last_seen_at=now,
        attributes={"database": "Db.with.dot", "schema": "Schema.with.dot"},
    )
    node = lineage_node(asset, counts=counts)
    relation = asset_type in {AssetType.TABLE, AssetType.VIEW, AssetType.MATERIALIZED_VIEW}
    assert node.database == ("Db.with.dot" if relation else None)
    assert node.schema_name == ("Schema.with.dot" if relation else None)
    asset.attributes["unresolved"] = True
    unresolved = lineage_node(asset, counts=counts)
    assert unresolved.unresolved
    assert unresolved.database is None
    assert unresolved.schema_name is None


@pytest.mark.parametrize("value", [None, "", "  ", 123, ["raw"], {"schema": "raw"}])
def test_unknown_membership_is_not_inferred_or_coerced(value):
    now = datetime.datetime.now(datetime.UTC)
    asset = Asset(
        asset_type=AssetType.TABLE,
        qualified_name="dwh.raw.table",
        name="raw.table",
        source_provider="test",
        identity_key="test",
        first_seen_at=now,
        last_seen_at=now,
        attributes={"database": value, "schema": value},
    )
    node = lineage_node(asset)
    assert node.database is None
    assert node.schema_name is None
