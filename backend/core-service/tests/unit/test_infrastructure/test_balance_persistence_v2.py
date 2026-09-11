"""Tests for the DataFrame-free Balance persistence planner."""

import datetime as dt
from types import SimpleNamespace

import pytest

from domains.risk.services.balance.persistence_v2 import BalancePersistencePlanner
from domains.risk.services.balance.persistence_v2.errors import RawValueError
from domains.risk.services.balance.persistence_v2.raw_values import classify_raw_value
from domains.risk.services.balance.persistence_v2.samples import normalized_sample_indices


def _node(raw_value):
    return SimpleNamespace(
        name="Node",
        node_path="root/node",
        gl_account="GL001",
        direction="ENTRY",
        items=[],
        calc_value=999.0,
        calc_value_raw=raw_value,
        model_source_values=raw_value,
        model_position="python://node",
        market=None,
        product=None,
        supply_path=None,
        legal_entity_id=None,
        allocation_profile_ref=None,
        persist_modelled_position=False,
    )


def test_one_element_raw_vector_is_scalar():
    value = classify_raw_value([12.5], node_key="node")

    assert value is not None
    assert value.is_simulation is False
    assert value.values == (12.5,)


def test_nested_raw_vector_is_rejected():
    with pytest.raises(RawValueError):
        classify_raw_value([[1.0, 2.0]], node_key="node")


def test_sample_selection_is_stable_and_keeps_identity_size():
    first = normalized_sample_indices(2, 5, seed_parts=("node", "source", "5"))
    second = normalized_sample_indices(2, 5, seed_parts=("node", "source", "5"))

    assert first == second
    assert len(first) == 5
    assert set(first) <= {0, 1}


def test_planner_materializes_one_element_vector_as_static_monthly_rows():
    plan = BalancePersistencePlanner().build_plan(
        SimpleNamespace(hierarchy=[_node([12.0])]),
        observation_date=dt.date(2026, 1, 1),
        valuation_type="eod",
        valuation_year=2026,
        target_sample_count=5,
        allocation_profiles=None,
        fx_values=[100.0],
    )

    assert plan.rows_count == 12
    rows = [row for _, partition_rows in plan.partitions for row in partition_rows]
    assert {row.run_mode for row in rows} == {"static"}
    assert {row.sample_index for row in rows} == {-2}


def test_static_article_expands_to_exactly_twelve_monthly_partitions():
    """One article must map to 12 monthly valuation partitions.

    The default joint monthly profile places a share in every valuation month,
    so a single scalar article produces exactly one physical partition for each
    month. No independent-share Cartesian product may multiply this fan-out.
    """
    first = _node([24.0])
    first.gl_account = "GL001"
    first.market = "m1"
    first.product = "p1"
    first.supply_path = "base"

    second = _node([48.0])
    second.node_path = "root/second"
    second.name = "Second"
    second.gl_account = "GL002"
    second.market = "__REST__"
    second.product = "__REST__"

    plan = BalancePersistencePlanner().build_plan(
        SimpleNamespace(hierarchy=[first, second]),
        observation_date=dt.date(2026, 1, 1),
        valuation_type="eod",
        valuation_year=2026,
        target_sample_count=5,
        allocation_profiles=None,
        fx_values=[100.0],
    )

    # Two articles x twelve months, exactly.
    articles: dict[tuple[str, str, str, str], set[str]] = {}
    for key, _ in plan.partitions:
        article = (key.gl_account, key.market, key.product, key.scenario)
        articles.setdefault(article, set()).add(key.valuation_month)

    assert len(plan.partitions) == 24
    assert len(articles) == 2
    assert {len(months) for months in articles.values()} == {12}

    # Each monthly partition of the first article owns exactly one scalar row.
    for key, rows in plan.partitions:
        if key.gl_account == "GL001":
            assert len(rows) == 1
            assert (
                key.valuation_month
                in articles[(key.gl_account, key.market, key.product, key.scenario)]
            )


def test_planner_normalizes_simulation_values_and_preserves_monthly_cells():
    plan = BalancePersistencePlanner().build_plan(
        SimpleNamespace(hierarchy=[_node([1.0, 2.0])]),
        observation_date=dt.date(2026, 1, 1),
        valuation_type="eod",
        valuation_year=2026,
        target_sample_count=5,
        allocation_profiles=None,
        fx_values=[100.0] * 5,
    )

    rows = [row for _, partition_rows in plan.partitions for row in partition_rows]
    assert len(rows) == 5 * 12
    assert {row.run_mode for row in rows} == {"simulation"}
    assert {row.sample_index for row in rows} == set(range(5))
    assert {row.payment_month for row in rows} == set(range(1, 13))


def test_planner_resamples_gl_tree_owned_simulation_values_when_source_is_shorter():
    node = _node([10.0, 20.0])
    node.model_position = "python://node.py"

    plan = BalancePersistencePlanner().build_plan(
        SimpleNamespace(hierarchy=[node]),
        observation_date=dt.date(2026, 1, 1),
        valuation_type="eod",
        valuation_year=2026,
        target_sample_count=5,
        allocation_profiles=None,
        fx_values=[100.0] * 5,
    )

    rows = [row for _, partition_rows in plan.partitions for row in partition_rows]
    assert {row.sample_index for row in rows} == set(range(5))
    assert all(
        any(row.value_rub == pytest.approx(expected) for expected in (10.0 / 12, 20.0 / 12))
        for row in rows
    )


def test_planner_classifies_deterministic_and_stochastic_values_into_separate_modes():
    # Проверяем, что детерминированное значение и готовая выборка сохраняются раздельно.
    deterministic = _node([12.0])
    stochastic = _node([10.0, 20.0])
    stochastic.node_path = "root/stochastic"

    plan = BalancePersistencePlanner().build_plan(
        SimpleNamespace(hierarchy=[deterministic, stochastic]),
        observation_date=dt.date(2026, 1, 1),
        valuation_type="eod",
        valuation_year=2026,
        target_sample_count=2,
        allocation_profiles=None,
        fx_values=[100.0] * 2,
    )

    rows = [row for _, partition_rows in plan.partitions for row in partition_rows]
    assert {row.run_mode for row in rows} == {"static", "simulation"}
    assert {row.sample_index for row in rows if row.run_mode == "static"} == {-2}
    assert {row.sample_index for row in rows if row.run_mode == "simulation"} == {0, 1}


def test_planner_skips_single_value_precomputed_contract_simulation():
    # Reduced contract values must not be resampled into GL-tree-owned rows.
    node = _node([42.0])
    node.model_position = "contract://?slug=contract1"

    plan = BalancePersistencePlanner().build_plan(
        SimpleNamespace(hierarchy=[node]),
        observation_date=dt.date(2026, 1, 1),
        valuation_type="eod",
        valuation_year=2026,
        target_sample_count=2,
        allocation_profiles=None,
        fx_values=[100.0] * 2,
    )

    assert plan.rows_count == 0


def test_planner_skips_multi_value_precomputed_contract_simulation():
    node = _node([10.0, 20.0])
    node.model_position = "contract://?gl_account=OP_TAX_DUTY"

    plan = BalancePersistencePlanner().build_plan(
        SimpleNamespace(hierarchy=[node]),
        observation_date=dt.date(2026, 1, 1),
        valuation_type="eod",
        valuation_year=2026,
        target_sample_count=5,
        allocation_profiles=None,
        fx_values=[100.0] * 5,
    )

    assert plan.rows_count == 0


def test_planner_keeps_single_value_deterministic_contract_as_static():
    # Проверяем, что только явный mode=deterministic разрешает статическую классификацию.
    node = _node([42.0])
    node.model_position = "contract://?slug=contract1&mode=deterministic"

    plan = BalancePersistencePlanner().build_plan(
        SimpleNamespace(hierarchy=[node]),
        observation_date=dt.date(2026, 1, 1),
        valuation_type="eod",
        valuation_year=2026,
        target_sample_count=2,
        allocation_profiles=None,
        fx_values=[100.0] * 2,
    )

    rows = [row for _, partition_rows in plan.partitions for row in partition_rows]
    assert {row.run_mode for row in rows} == {"static"}
    assert {row.sample_index for row in rows} == {-2}


def test_planner_recurses_into_children_of_modelled_parent():
    parent = _node(None)
    parent.model_position = "python://parent"
    parent.items = [_node([7.0])]
    parent.items[0].node_path = "root/parent/child"

    plan = BalancePersistencePlanner().build_plan(
        SimpleNamespace(hierarchy=[parent]),
        observation_date=dt.date(2026, 1, 1),
        valuation_type="eod",
        valuation_year=2026,
        target_sample_count=5,
        allocation_profiles=None,
        fx_values=[100.0],
    )

    rows = [row for _, partition_rows in plan.partitions for row in partition_rows]
    assert rows
    assert {row.gl_account for row in rows} == {"GL001"}


def test_planner_persists_entry_children_instead_of_parent_aggregate():
    parent = _node([100.0])
    parent.items = [_node([7.0])]
    parent.items[0].node_path = "root/parent/child"

    plan = BalancePersistencePlanner().build_plan(
        SimpleNamespace(hierarchy=[parent]),
        observation_date=dt.date(2026, 1, 1),
        valuation_type="eod",
        valuation_year=2026,
        target_sample_count=1,
        allocation_profiles=None,
        fx_values=[100.0],
    )

    rows = [row for _, partition_rows in plan.partitions for row in partition_rows]
    # The default allocation expands the authoritative child into monthly
    # cells; the parent's aggregate must not create a second set of rows.
    assert rows
    assert sum(row.value_rub for row in rows) == pytest.approx(7.0)
    assert all(row.value_rub != pytest.approx(100.0 / 12.0) for row in rows)
