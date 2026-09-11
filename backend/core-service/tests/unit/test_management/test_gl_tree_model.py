import pytest

from domains.management.models.gl_tree import (
    GlTreeAllocationProfileModel,
    GlTreeModel,
    GlTreeNodeModel,
)
from domains.risk.services.balance.allocation_policies import resolve_allocation_profiles


def test_gl_tree_node_model_supports_optional_result_slice_dimensions() -> None:
    node = GlTreeNodeModel(
        name="Revenue",
        gl_account="OP_REV_SALES",
        market="sales_fabr",
        product="pipelinegas",
        legal_entity="entity_a",
        supply_path="north_corridor",
    )

    dumped = node.model_dump()

    assert dumped["market"] == "sales_fabr"
    assert dumped["product"] == "pipelinegas"
    assert dumped["legal_entity"] == "entity_a"
    assert dumped["supply_path"] == "north_corridor"


def test_gl_tree_node_model_maps_persisted_position_names_independently() -> None:
    node = GlTreeNodeModel.model_validate(
        {
            "name": "Revenue",
            "monitor_position": "base://source",
            "query": "model://source",
        }
    )

    assert node.base_position == "base://source"
    assert node.model_position == "model://source"


def _profile_shares(*months: int) -> list[dict[str, float | int]]:
    share = 1.0 / len(months)
    return [{"valuation_month": month, "payment_month": month, "share": share} for month in months]


def _profile(profile_id: str) -> GlTreeAllocationProfileModel:
    return GlTreeAllocationProfileModel(
        id=profile_id,
        name=profile_id,
        kind="joint_month_shares",
        shares=_profile_shares(1, 2),
    )


def test_gl_tree_round_trips_allocation_profile_catalog_and_node_reference() -> None:
    tree = GlTreeModel(
        name="Cash Flow",
        allocation_profiles=[_profile("quarterly")],
        hierarchy=[GlTreeNodeModel(name="Costs", allocation_profile_ref="quarterly")],
    )

    dumped = tree.model_dump()

    assert dumped["allocation_profiles"][0]["id"] == "quarterly"
    assert dumped["allocation_profiles"][0]["shares"][1]["payment_month"] == 2
    assert dumped["hierarchy"][0]["allocation_profile_ref"] == "quarterly"


def test_default_profile_catalog_is_extended_by_tree_local_definition(tmp_path) -> None:
    (tmp_path / "balance-allocation-policies.json").write_text(
        '{"allocation_profiles": ['
        '{"id": "monthly", "name": "Monthly", "kind": "joint_month_shares", "shares": [{"valuation_month": 1, "payment_month": 1, "share": 1.0}]},'
        '{"id": "end_of_quarter", "name": "Quarter", "kind": "joint_month_shares", "shares": [{"valuation_month": 3, "payment_month": 3, "share": 1.0}]}]}',
        encoding="utf-8",
    )
    tree = GlTreeModel(name="Balance", allocation_profiles=[_profile("custom")])

    resolved = resolve_allocation_profiles(tree, str(tmp_path))

    assert set(resolved) == {"monthly", "end_of_quarter", "custom"}


def test_allocation_profile_rejects_invalid_shares() -> None:
    with pytest.raises(ValueError, match="sum to 1.0"):
        GlTreeAllocationProfileModel(
            id="invalid",
            name="Invalid",
            shares=[{"valuation_month": 1, "payment_month": 1, "share": 0.5}],
        )


def test_allocation_profile_rejects_legacy_shape() -> None:
    with pytest.raises(ValueError):
        GlTreeAllocationProfileModel.model_validate(
            {
                "id": "legacy",
                "name": "Legacy",
                "valuation": {"shares": [{"month": 1, "share": 1.0}]},
                "payment": {"shares": [{"month": 1, "share": 1.0}]},
            }
        )
