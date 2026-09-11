import datetime as dt

import pytest

from infrastructure.files.hive_path_builder import (
    PARTITION_COLUMNS,
    PartitionSentinel,
    YearlyAggregatePeriod,
    build_balance_tree_metadata_path,
    build_fact_glob_prefix,
    build_fact_partition_path,
    build_run_metadata_path,
    fact_dataset_path,
    normalize_partition_value,
    observation_discovery_root,
)


def test_complete_simulation_and_static_paths_share_date_first_dataset() -> None:
    common = dict(
        base_path="executions/data",
        observation_date=dt.date(2026, 5, 7),
        valuation_type="eod",
        gl_account="OP_REV_SALES",
        market="Europe",
        product="Oil",
    )
    simulation = build_fact_partition_path(
        **common,
        run_mode="simulation",
        valuation_period=dt.date(2026, 5, 1),
        scenario="base",
    )
    static = build_fact_partition_path(
        **common,
        run_mode="static",
        valuation_period=YearlyAggregatePeriod(2026),
        scenario=PartitionSentinel.ALL,
    )

    assert simulation == (
        "executions/data/fact_simulation/observation_date=20260507/"
        "run_mode=simulation/valuation_type=eod/valuation_year=2026/valuation_month=05/"
        "gl_account=OP_REV_SALES/market=Europe/product=Oil/scenario=base"
    )
    assert static == (
        "executions/data/fact_simulation/observation_date=20260507/"
        "run_mode=static/valuation_type=eod/valuation_year=2026/valuation_month=__REST__/"
        "gl_account=OP_REV_SALES/market=Europe/product=Oil/scenario=__ALL__"
    )
    assert PARTITION_COLUMNS == (
        "observation_date",
        "run_mode",
        "valuation_type",
        "valuation_year",
        "valuation_month",
        "gl_account",
        "market",
        "product",
        "scenario",
    )


@pytest.mark.parametrize("valuation_month", [1, "1", 11, "11"])
def test_explicit_valuation_month_is_zero_padded(valuation_month) -> None:
    path = build_fact_partition_path(
        "executions/data",
        observation_date=dt.date(2026, 5, 7),
        run_mode="simulation",
        valuation_type="eod",
        valuation_year=2026,
        valuation_month=valuation_month,
        gl_account=None,
        market=None,
        product=None,
        scenario=None,
    )

    expected_month = f"{int(valuation_month):02d}"
    assert f"valuation_month={expected_month}" in path


def test_partition_values_distinguish_null_and_aggregate_sentinels() -> None:
    assert normalize_partition_value(None) == "__HIVE_DEFAULT_PARTITION__"
    assert normalize_partition_value("") == "__HIVE_DEFAULT_PARTITION__"
    assert normalize_partition_value(float("nan")) == "__HIVE_DEFAULT_PARTITION__"
    assert normalize_partition_value(PartitionSentinel.REST) == "__REST__"
    assert normalize_partition_value(PartitionSentinel.ALL) == "__ALL__"
    assert normalize_partition_value("a/b\\c") == "a_b_c"


@pytest.mark.parametrize("period", [None, "", "not-a-date", "2026-13-01"])
def test_invalid_valuation_period_is_rejected(period) -> None:
    with pytest.raises(ValueError, match="valuation_period"):
        build_fact_partition_path(
            "executions/data",
            observation_date=dt.date(2026, 5, 7),
            run_mode="simulation",
            valuation_type="eod",
            valuation_period=period,
            gl_account=None,
            market=None,
            product=None,
            scenario=None,
        )


def test_wildcard_prefix_preserves_all_coarse_partition_levels() -> None:
    assert build_fact_glob_prefix("executions/data") == (
        "executions/data/fact_simulation/observation_date=*/run_mode=*/valuation_type=*"
    )
    assert build_fact_glob_prefix(
        "executions/data/fact_simulation",
        observation_date=dt.date(2026, 5, 7),
        run_mode="simulation",
    ) == (
        "executions/data/fact_simulation/observation_date=20260507/"
        "run_mode=simulation/valuation_type=*"
    )


def test_metadata_paths_and_discovery_use_the_canonical_dataset() -> None:
    assert build_run_metadata_path(
        "executions/data",
        observation_date=dt.date(2026, 5, 7),
        valuation_type="eod",
    ) == (
        "executions/data/fact_simulation/observation_date=20260507/"
        "run_mode=simulation/valuation_type=eod/_run_metadata.json"
    )
    assert build_balance_tree_metadata_path(
        "executions/data",
        observation_date=dt.date(2026, 5, 7),
        valuation_type="eod",
        valuation_year=2026,
    ) == (
        "executions/data/fact_simulation/observation_date=20260507/"
        "run_mode=static/valuation_type=eod/valuation_year=2026/_balance_tree_metadata.json"
    )
    assert fact_dataset_path("executions/data/fact_simulation") == fact_dataset_path(
        "executions/data"
    )
    assert observation_discovery_root("executions/data") == "executions/data/fact_simulation"


def test_current_fact_paths_exclude_speculative_partitions() -> None:
    path = build_fact_partition_path(
        "executions/data",
        observation_date=dt.date(2026, 5, 7),
        run_mode="simulation",
        valuation_type="eod",
        valuation_period=dt.date(2026, 5, 1),
        gl_account=None,
        market=None,
        product=None,
        scenario=None,
    )
    assert "execution_id=" not in path
    assert "simulation_type=" not in path
