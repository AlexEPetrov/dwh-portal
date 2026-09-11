"""Tests for the GL-tree save response sanitizer.

The save handler reuses the persistence-calculated tree for the API response
instead of running a second full calculation. The sanitizer must strip only the
write-side metadata (``persist_modelled_position`` and the
``__MODELLED_PROPAGATED__`` marker) while preserving every display field exactly
as the read path would produce it.
"""

import datetime as dt
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch
from uuid import uuid4

from domains.risk.models.gl_tree import GlCalculatedTreeModel, GlCalculatedTreeNodeModel
from domains.risk.services.balance.persistence_v2 import BalanceWritePlan
from domains.risk.services.balance.tree.application.gl_tree_commands import (
    GlTreeApplicationContext,
    SaveGlTreeCommand,
    SaveGlTreeCommandHandler,
    _response_tree_from_calculated,
)
from shared.cqrs.core import CommandContext


def _node(**overrides: Any) -> GlCalculatedTreeNodeModel:
    """Build a realistic calculated node with write-side metadata enabled."""
    fields: dict[str, Any] = {
        "name": "Node",
        "gl_account": "GL001",
        "base_report_value": 10.0,
        "base_source_values": [10.0],
        "model_report_value": 100.0,
        "model_source_values": [100.0, 120.0],
        "description": "desc",
        "direction": "ENTRY",
        "model_position": "python://node",
        "market": "m1",
        "product": "p1",
        "supply_path": "base",
        "legal_entity": "LE1",
        "allocation_profile_ref": "profile_a",
        "node_path": "root/node",
        "persist_modelled_position": True,
    }
    fields.update(overrides)
    return GlCalculatedTreeNodeModel(**fields)


def _tree(*nodes: GlCalculatedTreeNodeModel) -> GlCalculatedTreeNodeModel:
    return GlCalculatedTreeNodeModel(name="Root", items=list(nodes), node_path="root")


def test_response_tree_strips_persistence_metadata_only() -> None:
    root = _tree(_node())

    response = _response_tree_from_calculated(GlCalculatedTreeModel([root], 10.0, 500.0))

    result_root = response.hierarchy[0]
    result_child = result_root.items[0]

    # Tree totals survive.
    assert response.base_report_total == 10.0
    assert response.model_report_total == 500.0

    # Display fields survive untouched (raw vectors are populated on both paths).
    assert result_child.model_report_value == 100.0
    assert result_child.model_source_values == [100.0, 120.0]
    assert result_child.base_source_values == [10.0]
    assert result_child.model_position == "python://node"
    assert result_child.allocation_profile_ref == "profile_a"
    assert result_child.market == "m1"
    assert result_child.node_path == "root/node"

    # Write-side metadata is stripped.
    assert result_root.persist_modelled_position is False
    assert result_child.persist_modelled_position is False

    # The source persistence tree is not mutated.
    assert root.items[0].persist_modelled_position is True


def test_response_tree_hides_propagated_write_marker() -> None:
    node = _node(model_position="__MODELLED_PROPAGATED__")
    root = _tree(node)

    response = _response_tree_from_calculated(GlCalculatedTreeModel([root]))

    # The write-side marker must not leak to the API response.
    assert response.hierarchy[0].items[0].model_position is None
    assert node.model_position == "__MODELLED_PROPAGATED__"


def test_response_tree_recurses_through_nested_children() -> None:
    leaf = _node(name="Leaf", model_position="python://leaf")
    parent = _node(name="Parent", items=[leaf], model_source_values=None)
    root = _tree(parent)

    response = _response_tree_from_calculated(GlCalculatedTreeModel([root]))

    result_leaf = response.hierarchy[0].items[0].items[0]
    assert result_leaf.name == "Leaf"
    assert result_leaf.model_position == "python://leaf"
    assert result_leaf.persist_modelled_position is False
    assert parent.persist_modelled_position is True


def test_save_handler_calculates_once_and_reuses_sanitized_tree() -> None:
    """Save must not recalculate solely to construct the API response."""
    source_tree = GlCalculatedTreeModel([_tree(_node())], 10.0, 20.0)
    calculator = MagicMock()
    calculator.execute.return_value = source_tree
    tree_def = SimpleNamespace(
        slug="tree",
        name="Tree",
        options=SimpleNamespace(year=2026, currency="rub"),
    )
    metadata_service = MagicMock()
    app = GlTreeApplicationContext(
        repository=MagicMock(),
        metadata_service=metadata_service,
    )
    app.repository.get_first.return_value = tree_def
    command = SaveGlTreeCommand(
        request_id=uuid4(),
        gl_tree_slug="tree",
        observation_date=dt.date(2026, 8, 20),
        target_sample_count=1,
    )

    fx_result = SimpleNamespace(values=[SimpleNamespace(value=100.0)])
    empty_plan = BalanceWritePlan(())
    with (
        patch(
            "domains.risk.services.balance.tree.application.gl_tree_commands.prepare_save_fx_snapshot"
        ),
        patch(
            "domains.risk.services.balance.tree.application.gl_tree_commands.calculate_usdrub_year_avg",
            return_value=fx_result,
        ),
        patch(
            "domains.risk.services.balance.tree.application.gl_tree_commands.CalcServiceSettings",
            return_value=SimpleNamespace(grpc_sock="test-grpc-sock"),
        ),
        patch(
            "domains.risk.services.balance.tree.application.gl_tree_commands.build_balance_calculator",
            return_value=calculator,
        ) as build_calculator,
        patch(
            "domains.risk.services.balance.tree.application.gl_tree_commands.BalancePersistencePlanner.build_plan",
            return_value=empty_plan,
        ),
        patch(
            "domains.risk.services.balance.tree.application.gl_tree_commands.BalanceParquetWriter.write",
            return_value=0,
        ),
        patch(
            "domains.risk.services.balance.tree.application.gl_tree_commands.get_file_store_registry",
            return_value=SimpleNamespace(storage=None),
        ),
        patch(
            "domains.risk.services.balance.tree.application.gl_tree_commands.resolve_allocation_profiles",
            return_value=None,
        ),
        patch(
            "domains.risk.services.balance.tree.application.gl_tree_commands.LocationsSettings",
            return_value=SimpleNamespace(documents=""),
        ),
    ):
        result = SaveGlTreeCommandHandler(MagicMock(), app).execute(
            command,
            CommandContext(data={}, bus=MagicMock()),
        )

    build_calculator.assert_called_once()
    calculator.execute.assert_called_once_with()
    response = result.data["result"].calculated_tree
    assert response is not source_tree
    assert response.hierarchy[0].items[0].persist_modelled_position is False
    assert source_tree.hierarchy[0].items[0].persist_modelled_position is True
