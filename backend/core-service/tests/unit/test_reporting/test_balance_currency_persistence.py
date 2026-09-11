"""Tests for Balance-currency conversion during fact serialization."""

import datetime as dt
from types import SimpleNamespace

import numpy as np
import pytest

from domains.management.models.gl_tree import GlTreeAllocationProfileModel
from domains.risk.services.balance.persistence.balance_materializer import (
    ExcelPreflightError,
    ModelledSourceValue,
    build_excel_positions_dataframe,
    normalize_fx_values,
)
from domains.risk.services.balance.persistence.static_balance_writer import build_static_dataframe


def _node() -> SimpleNamespace:
    return SimpleNamespace(
        name="FX node",
        gl_account="GL001",
        market=None,
        product=None,
        supply_path=None,
        legal_entity=None,
        legal_entity_id=None,
        base_position=None,
        model_position=None,
        node_path=None,
        allocation_profile_ref=None,
        direction="ENTRY",
        items=[],
        calc_value=100.0,
        model_report_value=100.0,
        model_source_values=None,
    )


def _single_cell_monthly_profile() -> dict[str, GlTreeAllocationProfileModel]:
    profile = GlTreeAllocationProfileModel(
        id="monthly",
        name="Monthly test profile",
        shares=[{"valuation_month": 1, "payment_month": 1, "share": 1.0}],
    )
    return {"monthly": profile}


def test_rub_balance_derives_usd_for_static_and_simulation_values() -> None:
    node = _node()
    static = build_static_dataframe(
        [node],
        2026,
        balance_currency="rub",
        usdrub_year_avg=100.0,
        allocation_profiles=_single_cell_monthly_profile(),
    )
    simulation = build_excel_positions_dataframe(
        [
            ModelledSourceValue(
                node=node,
                values=np.array([100.0, 200.0]),
                value_usd_values=None,
                source_ref="python://values.py",
                is_simulation=True,
            )
        ],
        observation_date=dt.date(2026, 1, 1),
        valuation_year=2026,
        valuation_type="eod",
        balance_currency="rub",
        usdrub_year_avg=100.0,
        allocation_profiles=_single_cell_monthly_profile(),
    )

    assert static[["value_rub", "value_usd"]].iloc[0].tolist() == [100.0, 1.0]
    assert simulation[["value_rub", "value_usd"]].values.tolist() == [[100.0, 1.0], [200.0, 2.0]]


def test_dataset_modelled_value_is_converted_from_report_currency_before_save() -> None:
    from unittest.mock import MagicMock

    from domains.management.models.gl_tree import GlTreeModel, GlTreeNodeModel, GlTreeOptionsModel
    from domains.risk.services.balance.sources.modelled_balance_cell_resolver import (
        ModelledPositionValue,
    )
    from domains.risk.services.balance.tree.calculation.calculated_balance_tree import (
        BalanceCalculator,
    )

    tree = GlTreeModel(
        name="Balance",
        options=GlTreeOptionsModel(year=2026, currency="rub", report_currency="bln_rub"),
        hierarchy=[
            GlTreeNodeModel(
                name="Dataset",
                gl_account="GL001",
                model_position="dataset://DATASET?page_title=Assets",
            )
        ],
    )
    modelled = MagicMock()
    modelled.resolve_value.return_value = ModelledPositionValue(2.0, "dataset", "deterministic")
    calculated = BalanceCalculator(
        tree,
        dt.date(2026, 1, 1),
        scenario="default",
        monitored_position_service=MagicMock(),
        modelled_position_service=modelled,
        include_raw_values=True,
    ).execute()

    assert calculated.hierarchy[0].model_report_value == 2.0
    assert calculated.hierarchy[0].model_source_values == 2_000_000_000.0


def test_derived_other_value_is_converted_from_report_currency_before_save() -> None:
    from unittest.mock import MagicMock

    from domains.management.models.gl_tree import GlTreeModel, GlTreeNodeModel, GlTreeOptionsModel
    from domains.risk.services.balance.sources.modelled_balance_cell_resolver import (
        ModelledPositionValue,
    )
    from domains.risk.services.balance.tree.calculation.calculated_balance_tree import (
        BalanceCalculator,
    )

    parent_position = "dataset://DATASET?page_title=Assets&metric_name=Total"
    child_position = "dataset://DATASET?page_title=Assets&metric_name=Child"
    tree = GlTreeModel(
        name="Balance",
        options=GlTreeOptionsModel(year=2026, currency="rub", report_currency="bln_rub"),
        hierarchy=[
            GlTreeNodeModel(
                name="Parent",
                gl_account="GL001",
                base_position=parent_position,
                items=[
                    GlTreeNodeModel(
                        name="Child",
                        gl_account="GL001",
                        base_position=child_position,
                    )
                ],
            )
        ],
    )
    monitored = MagicMock()
    monitored.get_value.side_effect = lambda _date, position, *_args: {
        parent_position: 2.0,
        child_position: 1.0,
    }[position]
    modelled = MagicMock()
    modelled.resolve_value.return_value = ModelledPositionValue(None, "none", "deterministic")

    calculated = BalanceCalculator(
        tree,
        dt.date(2026, 1, 1),
        scenario="default",
        monitored_position_service=monitored,
        modelled_position_service=modelled,
        include_raw_values=True,
    ).execute()

    other = calculated.hierarchy[0].items[-1]
    assert other.name == "Другое"
    assert other.model_report_value == 1.0
    assert other.model_source_values == 1_000_000_000.0


def test_base_dataset_value_propagated_to_model_is_converted_before_save() -> None:
    from unittest.mock import MagicMock

    from domains.management.models.gl_tree import GlTreeModel, GlTreeNodeModel, GlTreeOptionsModel
    from domains.risk.services.balance.sources.modelled_balance_cell_resolver import (
        ModelledPositionValue,
    )
    from domains.risk.services.balance.tree.calculation.calculated_balance_tree import (
        BalanceCalculator,
    )

    base_position = "dataset://DATASET?page_title=Assets&metric_name=Cash"
    tree = GlTreeModel(
        name="Balance",
        options=GlTreeOptionsModel(year=2026, currency="rub", report_currency="bln_rub"),
        hierarchy=[GlTreeNodeModel(name="Cash", gl_account="GL001", base_position=base_position)],
    )
    monitored = MagicMock()
    monitored.get_value.return_value = 2.0
    modelled = MagicMock()
    modelled.resolve_value.return_value = ModelledPositionValue(None, "none", "deterministic")

    calculated = BalanceCalculator(
        tree,
        dt.date(2026, 1, 1),
        scenario="default",
        monitored_position_service=monitored,
        modelled_position_service=modelled,
        include_raw_values=True,
    ).execute()

    node = calculated.hierarchy[0]
    assert node.model_report_value == 2.0
    assert node.model_source_values == 2_000_000_000.0


def test_usd_balance_derives_rub_for_simulation_values() -> None:
    node = _node()
    frame = build_excel_positions_dataframe(
        [
            ModelledSourceValue(
                node=node,
                values=np.array([1.5, 2.5]),
                value_usd_values=None,
                source_ref="file://values.xlsx|Sheet1|A1:A2",
                is_simulation=True,
            )
        ],
        observation_date=dt.date(2026, 1, 1),
        valuation_year=2026,
        valuation_type="eod",
        balance_currency="usd",
        usdrub_year_avg=100.0,
        allocation_profiles=_single_cell_monthly_profile(),
    )

    assert frame[["value_rub", "value_usd"]].values.tolist() == [[150.0, 1.5], [250.0, 2.5]]


def test_simulation_fx_is_applied_per_sample() -> None:
    node = _node()
    frame = build_excel_positions_dataframe(
        [
            ModelledSourceValue(
                node=node,
                values=np.array([100.0, 100.0]),
                value_usd_values=None,
                source_ref="python://values.py",
                is_simulation=True,
            )
        ],
        observation_date=dt.date(2026, 1, 1),
        valuation_year=2026,
        valuation_type="eod",
        balance_currency="rub",
        usdrub_year_avg_values=np.array([100.0, 125.0]),
        allocation_profiles=_single_cell_monthly_profile(),
    )

    assert frame[["sample_index", "value_rub", "value_usd"]].values.tolist() == [
        [0, 100.0, 1.0],
        [1, 100.0, 0.8],
    ]


def test_simulation_fx_requires_aligned_complete_samples() -> None:
    with np.testing.assert_raises(ExcelPreflightError):
        normalize_fx_values([100.0], expected_count=2)
    with np.testing.assert_raises(ExcelPreflightError):
        normalize_fx_values([100.0, 0.0], expected_count=2)


def test_annual_modelled_value_uses_profiled_valuation_and_payment_cells() -> None:
    node = _node()
    node.allocation_profile_ref = "q"
    profile = GlTreeAllocationProfileModel(
        id="q",
        name="Quarterly",
        shares=[{"valuation_month": 3, "payment_month": 6, "share": 1.0}],
    )
    frame = build_excel_positions_dataframe(
        [ModelledSourceValue(node, np.array([120.0]), "constant", False)],
        observation_date=dt.date(2026, 1, 1),
        valuation_year=2026,
        valuation_type="eod",
        usdrub_year_avg=100.0,
        allocation_profiles={"q": profile},
    )
    assert frame[
        ["valuation_month", "payment_year", "payment_month", "value_rub"]
    ].values.tolist() == [[3, 2026, 6, 120.0]]


def test_annual_modelled_value_uses_monthly_profile_by_default() -> None:
    node = _node()
    node.allocation_profile_ref = None
    monthly = GlTreeAllocationProfileModel(
        id="monthly",
        name="Monthly",
        shares=[
            {"valuation_month": month, "payment_month": month, "share": 1 / 12}
            for month in range(1, 13)
        ],
    )
    frame = build_excel_positions_dataframe(
        [ModelledSourceValue(node, np.array([120.0]), "constant", False)],
        observation_date=dt.date(2026, 1, 1),
        valuation_year=2026,
        valuation_type="eod",
        usdrub_year_avg=100.0,
        allocation_profiles={"monthly": monthly},
    )
    assert len(frame) == 12
    assert frame[["valuation_month", "payment_month", "value_rub"]].values.tolist() == [
        [month, month, 120.0 / 12.0] for month in range(1, 13)
    ]


def test_annual_modelled_value_supports_monthly_valuation_quarterly_payment() -> None:
    node = _node()
    node.allocation_profile_ref = "paid_quarter_end"
    profile = GlTreeAllocationProfileModel(
        id="paid_quarter_end",
        name="Monthly valuation, quarter-end payment",
        shares=[
            {"valuation_month": v, "payment_month": p, "share": 1 / 12}
            for v, p in [
                (1, 3),
                (2, 3),
                (3, 3),
                (4, 6),
                (5, 6),
                (6, 6),
                (7, 9),
                (8, 9),
                (9, 9),
                (10, 12),
                (11, 12),
                (12, 12),
            ]
        ],
    )
    frame = build_excel_positions_dataframe(
        [ModelledSourceValue(node, np.array([120.0]), "constant", False)],
        observation_date=dt.date(2026, 1, 1),
        valuation_year=2026,
        valuation_type="eod",
        usdrub_year_avg=100.0,
        allocation_profiles={"paid_quarter_end": profile},
    )
    assert len(frame) == 12
    month = frame.groupby("payment_month")["value_rub"].sum()
    assert month.loc[3] == pytest.approx(30.0)
    assert month.loc[6] == pytest.approx(30.0)
    assert month.loc[9] == pytest.approx(30.0)
    assert month.loc[12] == pytest.approx(30.0)


def test_modelled_persistence_excludes_parent_aggregates_and_reverse_nodes() -> None:
    parent = SimpleNamespace(
        name="Parent",
        gl_account="PARENT",
        direction="ENTRY",
        items=[],
        model_position="python://parent",
        base_position=None,
        persist_modelled_position=False,
        calc_value_raw=None,
    )
    child = SimpleNamespace(
        name="Child",
        gl_account="CHILD",
        direction="ENTRY",
        items=[],
        model_position="python://child",
        base_position=None,
        persist_modelled_position=False,
        calc_value_raw=100.0,
    )
    reverse = SimpleNamespace(
        name="Reverse",
        gl_account="REVERSE",
        direction="REVERSE",
        items=[],
        model_position="python://reverse",
        base_position=None,
        persist_modelled_position=False,
        calc_value_raw=-100.0,
    )
    parent.items = [child, reverse]
    parent.calc_value_raw = 100.0
    child.calc_value_raw = 100.0
    reverse.calc_value_raw = -100.0
    parent.model_source_values = None
    child.model_source_values = [100.0]
    reverse.model_source_values = [-100.0]
    from domains.risk.services.balance.persistence.balance_materializer import (
        resolve_modelled_sources_from_model_source_values,
    )

    resolved = resolve_modelled_sources_from_model_source_values(
        SimpleNamespace(hierarchy=[parent]), target_sample_count=1
    )
    assert [source.node.name for source in resolved] == ["Child"]


def test_derived_monitoring_position_does_not_require_allocation_profile() -> None:
    node = _node()
    monthly = GlTreeAllocationProfileModel(
        id="monthly",
        name="Monthly",
        shares=[
            {"valuation_month": month, "payment_month": month, "share": 1 / 12}
            for month in range(1, 13)
        ],
    )
    frame = build_excel_positions_dataframe(
        [ModelledSourceValue(node, np.array([120.0]), "monitoring residual", False)],
        observation_date=dt.date(2026, 1, 1),
        valuation_year=2026,
        valuation_type="eod",
        usdrub_year_avg=100.0,
        allocation_profiles={"monthly": monthly},
    )
    assert len(frame) == 12
