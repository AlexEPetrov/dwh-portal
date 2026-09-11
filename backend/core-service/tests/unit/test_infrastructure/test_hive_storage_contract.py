"""Regression tests for fact dataset routing and managed Hive ownership."""

import datetime as dt
import json
from pathlib import Path

import pandas as pd
import pytest

from domains.risk.services.balance.persistence.balance_materializer import (
    ExcelPreflightError,
)
from domains.risk.services.balance.persistence.hive_partition_policy import (
    HiveOwnershipConflictError,
    preflight_hive_write_plan,
    write_metainfo,
)
from domains.risk.services.balance.persistence.simulation_balance_writer import (
    write_simulation_parquet_files,
)
from domains.risk.services.balance.persistence.static_balance_writer import (
    write_static_parquet_files,
)
from infrastructure.files.hive_path_builder import (
    build_fact_partition_path,
    dataset_for_run_mode,
)


def _rows(run_mode: str) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "observation_date": [dt.date(2026, 8, 20)],
            "run_mode": [run_mode],
            "valuation_type": ["custom_type"],
            "valuation_year": [2026],
            "valuation_month": ["__HIVE_DEFAULT_PARTITION__"],
            "gl_account": ["GL001"],
            "market": ["__REST__"],
            "product": ["__REST__"],
            "scenario": ["__REST__"],
            "legal_entity": ["LE001"],
            "payment_year": pd.array([2026], dtype="Int64"),
            "payment_month": pd.array([None], dtype="Int64"),
            "sample_index": [-2 if run_mode == "static" else 0],
            "value_rub": [100.0],
            "value_usd": [1.0],
            "description": [None],
            "volume": [0.0],
        }
    )


def _partition(base: Path, run_mode: str) -> Path:
    return Path(
        build_fact_partition_path(
            base,
            observation_date=dt.date(2026, 8, 20),
            run_mode=run_mode,
            valuation_type="custom_type",
            valuation_year=2026,
            valuation_month="__HIVE_DEFAULT_PARTITION__",
            gl_account="GL001",
            market="__REST__",
            product="__REST__",
            scenario="__REST__",
        )
    )


def test_all_result_modes_route_to_their_only_fact_dataset(tmp_path: Path) -> None:
    assert dataset_for_run_mode("deterministic") == "fact_deterministic"
    assert dataset_for_run_mode("simulation") == "fact_simulation"
    assert dataset_for_run_mode("static") == "fact_simulation"

    deterministic_path = _partition(tmp_path, "deterministic")
    simulation_path = _partition(tmp_path, "simulation")
    static_path = _partition(tmp_path, "static")

    assert "fact_deterministic" in deterministic_path.parts
    assert "fact_simulation" in simulation_path.parts
    assert "fact_simulation" in static_path.parts
    assert "fact_deterministic" not in simulation_path.parts
    assert "fact_deterministic" not in static_path.parts


@pytest.mark.parametrize(
    ("run_mode", "expected_dataset"),
    [("deterministic", "fact_simulation"), ("simulation", "fact_deterministic")],
)
def test_invalid_dataset_run_mode_combinations_are_rejected(
    tmp_path: Path, run_mode: str, expected_dataset: str
) -> None:
    with pytest.raises(ValueError, match="cannot be written"):
        build_fact_partition_path(
            tmp_path / expected_dataset,
            observation_date=dt.date(2026, 8, 20),
            run_mode=run_mode,
            valuation_type="eod",
            valuation_year=2026,
            valuation_month="05",
            gl_account="GL001",
            market="M1",
            product="P1",
            scenario="S1",
        )


def test_static_and_simulation_writers_publish_readable_owned_partitions(tmp_path: Path) -> None:
    simulation_df = _rows("simulation")
    static_df = _rows("static")

    simulation_root = tmp_path / "simulation-root"
    static_root = tmp_path / "static-root"
    assert write_simulation_parquet_files(None, simulation_df, str(simulation_root)) == 1
    assert write_static_parquet_files(None, static_df, str(static_root)) == 1

    for root, run_mode in ((simulation_root, "simulation"), (static_root, "static")):
        partition = _partition(root, run_mode)
        assert (partition / "data.parquet").exists()
        assert json.loads((partition / "metainfo.json").read_text())["producer"] == "gl_tree"
        assert len(pd.read_parquet(partition / "data.parquet")) == 1


def test_unknown_target_ownership_fails_before_physical_write(tmp_path: Path) -> None:
    partition = _partition(tmp_path, "static")
    partition.mkdir(parents=True)
    (partition / "data.parquet").write_bytes(b"existing")

    with pytest.raises(HiveOwnershipConflictError, match="no metainfo.json"):
        preflight_hive_write_plan(
            None,
            hive_base_path=str(tmp_path),
            frames=[("static", _rows("static"))],
        )

    assert (partition / "data.parquet").read_bytes() == b"existing"


def test_foreign_target_ownership_fails_before_physical_write(tmp_path: Path) -> None:
    partition = _partition(tmp_path, "static")
    partition.mkdir(parents=True)
    (partition / "data.parquet").write_bytes(b"foreign")
    write_metainfo(None, str(partition), producer="price_valuation_service")

    with pytest.raises(HiveOwnershipConflictError, match="price_valuation_service"):
        write_static_parquet_files(None, _rows("static"), str(tmp_path))

    assert (partition / "data.parquet").read_bytes() == b"foreign"


def test_writer_owned_simulation_counterpart_is_replaced_by_static(tmp_path: Path) -> None:
    simulation_partition = _partition(tmp_path, "simulation")
    simulation_partition.mkdir(parents=True)
    (simulation_partition / "data.parquet").write_bytes(b"old")
    write_metainfo(None, str(simulation_partition), producer="gl_tree")

    write_static_parquet_files(None, _rows("static"), str(tmp_path))

    assert not (simulation_partition / "data.parquet").exists()
    assert not (simulation_partition / "metainfo.json").exists()
    assert (_partition(tmp_path, "static") / "data.parquet").exists()


def test_physical_writers_reject_the_other_run_mode_before_writing(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Static writer accepts only"):
        write_static_parquet_files(None, _rows("simulation"), str(tmp_path / "static"))

    with pytest.raises(ExcelPreflightError, match="Simulation writer accepts only"):
        write_simulation_parquet_files(None, _rows("static"), str(tmp_path / "simulation"))


def test_one_save_plan_rejects_static_and_simulation_for_same_partition(tmp_path: Path) -> None:
    # Одна логическая позиция не может одновременно иметь static- и simulation-партиции.
    with pytest.raises(HiveOwnershipConflictError, match="Conflicting static/simulation"):
        preflight_hive_write_plan(
            None,
            hive_base_path=str(tmp_path),
            frames=[
                ("static", _rows("static")),
                ("simulation", _rows("simulation")),
            ],
        )
