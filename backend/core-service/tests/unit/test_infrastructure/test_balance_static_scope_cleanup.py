"""Tests for replacement of the complete Balance static save scope."""

import datetime as dt
import json
from pathlib import Path

import pytest

from domains.risk.services.balance.persistence.hive_partition_policy import (
    GL_TREE_PRODUCER,
    HiveOwnershipConflictError,
    preflight_and_delete_static_scope,
    static_scope_path,
)


def _write_partition(root: Path, relative: str, producer: str | None) -> Path:
    partition = root / relative
    partition.mkdir(parents=True)
    (partition / "data.parquet").write_bytes(b"old")
    if producer is not None:
        (partition / "metainfo.json").write_text(
            json.dumps({"producer": producer}), encoding="utf-8"
        )
    return partition


def test_cleanup_removes_old_gl_account_but_preserves_other_scopes(tmp_path: Path) -> None:
    base = "executions/data/fact_simulation"
    scope = static_scope_path(
        hive_base_path=base,
        observation_date=dt.date(2026, 6, 1),
        valuation_type="eod",
        valuation_year=2026,
    )
    old = _write_partition(
        tmp_path,
        f"{scope}/valuation_month=__NULL__/gl_account=OLD/market=__NULL__/"
        "product=__NULL__/scenario=default",
        GL_TREE_PRODUCER,
    )
    other_year = _write_partition(
        tmp_path,
        f"{base}/observation_date=20260601/run_mode=static/valuation_type=eod/"
        "valuation_year=2027/valuation_month=__NULL__/gl_account=KEEP/market=__NULL__/"
        "product=__NULL__/scenario=default",
        GL_TREE_PRODUCER,
    )

    deleted = preflight_and_delete_static_scope(
        None,
        hive_base_path=str(tmp_path / base),
        observation_date=dt.date(2026, 6, 1),
        valuation_type="eod",
        valuation_year=2026,
    )

    assert deleted == 1
    assert not (old / "data.parquet").exists()
    assert not (old / "metainfo.json").exists()
    assert other_year.exists()


def test_cleanup_fails_before_deleting_any_partition_on_foreign_owner(tmp_path: Path) -> None:
    base = tmp_path / "executions/data/fact_simulation"
    scope = static_scope_path(
        hive_base_path=str(base),
        observation_date=dt.date(2026, 6, 1),
        valuation_type="eod",
        valuation_year=2026,
    )
    first = _write_partition(
        tmp_path,
        f"{scope}/valuation_month=__NULL__/gl_account=FIRST/market=__NULL__/"
        "product=__NULL__/scenario=default",
        GL_TREE_PRODUCER,
    )
    foreign = _write_partition(
        tmp_path,
        f"{scope}/valuation_month=__NULL__/gl_account=FOREIGN/market=__NULL__/"
        "product=__NULL__/scenario=default",
        "price_valuation_service",
    )

    with pytest.raises(HiveOwnershipConflictError):
        preflight_and_delete_static_scope(
            None,
            hive_base_path=str(base),
            observation_date=dt.date(2026, 6, 1),
            valuation_type="eod",
            valuation_year=2026,
        )

    assert (first / "data.parquet").exists()
    assert foreign.exists()
