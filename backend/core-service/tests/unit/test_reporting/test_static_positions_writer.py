"""Tests for static_positions_writer eligibility and path-building logic."""

import numpy as np
import pandas as pd
import pytest

from domains.risk.models.gl_tree import GlCalculatedTreeNodeModel
from domains.risk.services.balance.persistence.static_balance_writer import (
    _raw_value_is_simulation,
    build_static_dataframe,
    collect_eligible_nodes,
    is_eligible_static_leaf,
)


@pytest.mark.parametrize(
    "value",
    [
        pd.DataFrame(),
        pd.Series(dtype=float),
        np.array([], dtype=float),
        [],
        (),
    ],
)
def test_empty_raw_values_are_not_simulation(value):
    """Empty raw containers do not own a node's static persistence."""
    assert _raw_value_is_simulation(value) is False


@pytest.mark.parametrize(
    "value",
    [
        pd.DataFrame({"value": [1.0, 2.0]}),
        pd.Series([1.0, 2.0]),
        np.array([1.0, 2.0]),
        [1.0, 2.0],
        (1.0, 2.0),
    ],
)
def test_multi_sample_raw_values_are_simulation(value):
    assert _raw_value_is_simulation(value) is True


@pytest.mark.parametrize(
    "value",
    [
        pd.DataFrame({"value": [1.0]}),
        pd.Series([1.0]),
        np.array([1.0]),
        [1.0],
        (1.0,),
        1.0,
    ],
)
def test_single_raw_values_are_not_simulation(value):
    assert _raw_value_is_simulation(value) is False


class TestIsEligibleStaticLeaf:
    """Test the is_eligible_static_leaf predicate."""

    def test_leaf_node_with_calc_value_is_eligible(self):
        node = GlCalculatedTreeNodeModel(
            name="Test Leaf",
            gl_account="OP_REV_SALES",
            base_report_value=100.0,
        )
        assert is_eligible_static_leaf(node) is True

    def test_leaf_node_without_calc_value_is_not_eligible(self):
        node = GlCalculatedTreeNodeModel(
            name="Test Leaf",
            gl_account="OP_REV_SALES",
            base_report_value=None,
        )
        assert is_eligible_static_leaf(node) is False

    def test_simulated_leaf_is_not_eligible(self):
        node = GlCalculatedTreeNodeModel(
            name="Simulated",
            gl_account="OP_REV_SALES",
            base_report_value=100.0,
            model_position="contract://position",
        )
        assert is_eligible_static_leaf(node) is False

    def test_reversed_node_is_not_eligible(self):
        node = GlCalculatedTreeNodeModel(
            name="Reversed",
            gl_account="OP_REV_SALES",
            base_report_value=100.0,
            direction="REVERSE",
        )
        assert is_eligible_static_leaf(node) is False

    def test_parent_with_all_reversed_children_is_eligible(self):
        child1 = GlCalculatedTreeNodeModel(
            name="Child 1",
            base_report_value=50.0,
            direction="REVERSE",
        )
        child2 = GlCalculatedTreeNodeModel(
            name="Child 2",
            base_report_value=50.0,
            direction="REVERSE",
        )
        parent = GlCalculatedTreeNodeModel(
            name="Parent",
            gl_account="OP_REV_SALES",
            base_report_value=100.0,
            items=[child1, child2],
        )
        # Parent has calc_value and all children are reversed
        assert is_eligible_static_leaf(parent) is True

    def test_parent_with_mixed_children_is_not_eligible(self):
        child1 = GlCalculatedTreeNodeModel(
            name="Child 1",
            base_report_value=50.0,
            direction="ENTRY",
        )
        child2 = GlCalculatedTreeNodeModel(
            name="Child 2",
            base_report_value=50.0,
            direction="REVERSE",
        )
        parent = GlCalculatedTreeNodeModel(
            name="Parent",
            gl_account="OP_REV_SALES",
            base_report_value=100.0,
            items=[child1, child2],
        )
        # Parent has calc_value but not all children are reversed
        assert is_eligible_static_leaf(parent) is False

    def test_const_node_is_eligible(self):
        node = GlCalculatedTreeNodeModel(
            name="Constant",
            gl_account="OP_REV_SALES",
            base_report_value=100.0,
            data_source_type="const",
        )
        assert is_eligible_static_leaf(node) is True

    def test_none_data_source_type_is_eligible(self):
        node = GlCalculatedTreeNodeModel(
            name="None Type",
            gl_account="OP_REV_SALES",
            calc_value=100.0,
            data_source_type=None,
        )
        assert is_eligible_static_leaf(node) is True


class TestCollectEligibleNodes:
    """Test the collect_eligible_nodes recursive collector."""

    def test_collect_simple_tree(self):
        leaf1 = GlCalculatedTreeNodeModel(
            name="Leaf 1",
            gl_account="OP_REV_SALES",
            calc_value=100.0,
        )
        leaf2 = GlCalculatedTreeNodeModel(
            name="Leaf 2",
            gl_account="OP_COST_COGS",
            calc_value=50.0,
        )
        root = GlCalculatedTreeNodeModel(
            name="Root",
            items=[leaf1, leaf2],
        )
        eligible = collect_eligible_nodes(root)
        assert len(eligible) == 2
        assert leaf1 in eligible
        assert leaf2 in eligible

    def test_collect_skips_simulated_leaves(self):
        leaf1 = GlCalculatedTreeNodeModel(
            name="Static Leaf",
            gl_account="OP_REV_SALES",
            calc_value=100.0,
        )
        leaf2 = GlCalculatedTreeNodeModel(
            name="Simulated Leaf",
            gl_account="OP_COST_COGS",
            calc_value=50.0,
            model_position="contract://position",
        )
        root = GlCalculatedTreeNodeModel(
            name="Root",
            items=[leaf1, leaf2],
        )
        eligible = collect_eligible_nodes(root)
        assert len(eligible) == 1
        assert leaf1 in eligible
        assert leaf2 not in eligible

    def test_collect_skips_reversed_nodes(self):
        leaf1 = GlCalculatedTreeNodeModel(
            name="ENTRY Leaf",
            gl_account="OP_REV_SALES",
            calc_value=100.0,
        )
        leaf2 = GlCalculatedTreeNodeModel(
            name="REVERSE Leaf",
            gl_account="OP_COST_COGS",
            calc_value=50.0,
            direction="REVERSE",
        )
        root = GlCalculatedTreeNodeModel(
            name="Root",
            items=[leaf1, leaf2],
        )
        eligible = collect_eligible_nodes(root)
        assert len(eligible) == 1
        assert leaf1 in eligible
        assert leaf2 not in eligible

    def test_collect_nested_tree(self):
        leaf1 = GlCalculatedTreeNodeModel(
            name="Leaf 1",
            gl_account="OP_REV_SALES",
            calc_value=100.0,
        )
        leaf2 = GlCalculatedTreeNodeModel(
            name="Leaf 2",
            gl_account="OP_COST_COGS",
            calc_value=50.0,
        )
        middle = GlCalculatedTreeNodeModel(
            name="Middle",
            items=[leaf2],
        )
        root = GlCalculatedTreeNodeModel(
            name="Root",
            items=[leaf1, middle],
        )
        eligible = collect_eligible_nodes(root)
        assert len(eligible) == 2
        assert leaf1 in eligible
        assert leaf2 in eligible

    def test_collect_parent_with_all_reversed_children(self):
        child1 = GlCalculatedTreeNodeModel(
            name="Child 1",
            calc_value=50.0,
            direction="REVERSE",
        )
        child2 = GlCalculatedTreeNodeModel(
            name="Child 2",
            calc_value=50.0,
            direction="REVERSE",
        )
        parent = GlCalculatedTreeNodeModel(
            name="Parent",
            gl_account="OP_REV_SALES",
            calc_value=100.0,
            items=[child1, child2],
        )
        root = GlCalculatedTreeNodeModel(
            name="Root",
            items=[parent],
        )
        eligible = collect_eligible_nodes(root)
        # Parent should be collected (all children reversed)
        assert len(eligible) == 1
        assert parent in eligible
        # Children should NOT be collected (they are REVERSE)
        assert child1 not in eligible
        assert child2 not in eligible


def test_collect_empty_tree():
    root = GlCalculatedTreeNodeModel(name="Empty Root", items=[])
    eligible = collect_eligible_nodes(root)
    assert len(eligible) == 0


def test_static_writer_preserves_explicit_market_and_product_dimensions():
    node = GlCalculatedTreeNodeModel(
        name="Product leaf",
        gl_account="GL001",
        market="M1",
        product="P1",
        calc_value=100.0,
    )
    frame = build_static_dataframe(
        [node],
        2026,
        usdrub_year_avg=100.0,
        allocation_profiles={
            "monthly": {
                "kind": "joint_month_shares",
                "shares": [{"valuation_month": 1, "payment_month": 1, "share": 1.0}],
            }
        },
    )
    assert frame[["market", "product"]].iloc[0].tolist() == ["M1", "P1"]


def test_static_writer_uses_uri_dimensions_when_node_dimensions_are_empty():
    node = GlCalculatedTreeNodeModel(
        name="URI product leaf",
        gl_account="GL001",
        base_position="contract://?market=M2&product=P2",
        calc_value=100.0,
    )
    frame = build_static_dataframe(
        [node],
        2026,
        usdrub_year_avg=100.0,
        allocation_profiles={
            "monthly": {
                "kind": "joint_month_shares",
                "shares": [{"valuation_month": 1, "payment_month": 1, "share": 1.0}],
            }
        },
    )
    assert frame[["market", "product"]].iloc[0].tolist() == ["M2", "P2"]


def test_static_rows_store_missing_volume_as_null():
    node = GlCalculatedTreeNodeModel(name="Static leaf", gl_account="GL001", calc_value=12.0)
    frame = build_static_dataframe([node], 2026, usdrub_year_avg=100.0)

    assert pd.isna(frame.iloc[0]["volume"])


def test_static_rows_store_unspecified_supply_path_as_rest():
    node = GlCalculatedTreeNodeModel(name="Static leaf", gl_account="GL001", calc_value=12.0)
    frame = build_static_dataframe([node], 2026, usdrub_year_avg=100.0)

    assert frame.iloc[0]["scenario"] == "__REST__"
