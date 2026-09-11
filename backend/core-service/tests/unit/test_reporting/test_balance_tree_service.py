"""Tests for BalanceTreeService hybrid query generation."""

import datetime as dt
from unittest.mock import MagicMock

from domains.management.models.gl_tree import GlTreeModel, GlTreeNodeModel
from domains.risk.services.balance.tree.calculation.simulation_balance_tree import (
    BalanceTreeService,
)


def test_hybrid_tree_ignores_new_contract_uri_filters() -> None:
    """Saved Balance does not narrow the complete fact_simulation partition by tree URI."""
    mock_sql_service = MagicMock()
    mock_sql_service.execute_query.return_value = (
        ["sample_index", "value_rub"],
        [[0, 10.0], [1, 20.0]],
        1.0,
    )
    service = BalanceTreeService(
        monitored_position_service=MagicMock(),
        modelled_position_service=MagicMock(),
        sql_query_service=mock_sql_service,
    )
    tree = GlTreeModel(
        name="sensitivity",
        hierarchy=[
            GlTreeNodeModel(
                name="gas sales",
                model_position="contract://?product=gas&market=sales_rus",
            )
        ],
    )

    result = service.calculate_hybrid_simulation_tree(tree, dt.date(2026, 5, 8))

    assert result.tolist() == [10.0, 20.0]
    sql = mock_sql_service.execute_query.call_args.args[0]
    assert "product = 'gas'" not in sql
    assert "market = 'sales_rus'" not in sql


def test_hybrid_tree_ignores_legacy_internal_contract_uri_filters() -> None:
    """Legacy tree URI dimensions are not a saved Balance row-level selector."""
    mock_sql_service = MagicMock()
    mock_sql_service.execute_query.return_value = (
        ["sample_index", "value_rub"],
        [[0, 10.0]],
        1.0,
    )
    service = BalanceTreeService(
        monitored_position_service=MagicMock(),
        modelled_position_service=MagicMock(),
        sql_query_service=mock_sql_service,
    )
    tree = GlTreeModel(
        name="legacy",
        hierarchy=[
            GlTreeNodeModel(
                name="legacy contracts",
                model_position="internal://contracts?gl_account=GL_TAX_1&counterparty=OOO_Example",
            )
        ],
    )

    service.calculate_hybrid_simulation_tree(tree, dt.date(2026, 5, 8))

    sql = mock_sql_service.execute_query.call_args.args[0]
    assert "gl_account = 'GL_TAX_1'" not in sql
    assert "counterparty = 'OOO_Example'" not in sql
