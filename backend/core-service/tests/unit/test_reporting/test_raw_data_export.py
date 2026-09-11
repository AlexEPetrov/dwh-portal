import csv
import datetime as dt
import zipfile

import numpy as np
import pandas as pd
from gp134.tools.storage_lib import StorageFS
from gp134.tools.storage_lib.backends.local_backend import LocalBackend

from domains.reporting.services.raw_data_export import (
    RawDataExportService,
    build_wrapped_simulation_sql,
)
from domains.reporting.services.simulation_query_service import SimulationQueryService
from infrastructure.analytics.duckdb_storage_adapter import DuckDbStorageAdapter


class _BalanceSourceStub:
    def load_balance_samples(self, request):
        assert request.balance_tree_slug == "cash-flow"
        assert request.scenario == "base"
        assert request.valuation_type == "eod"
        return np.array([30.0, 10.0, 20.0])


def _write_fact_simulation_dataset(base_dir):
    rows = [
        {
            "sample_index": 0,
            "scenario": "base",
            "market": "sales_fabr",
            "product": "pipelinegas",
            "gl_account": "OP_REV_SALES",
            "payment_period": "2026-01",
            "valuation_period": "2026-01-01",
            "value_rub": 100.0,
            "value_usd": 1.0,
            "volume": 10.0,
        },
        {
            "sample_index": 1,
            "scenario": "base",
            "market": "sales_fabr",
            "product": "pipelinegas",
            "gl_account": "OP_REV_SALES",
            "payment_period": "2026-01",
            "valuation_period": "2026-01-01",
            "value_rub": 200.0,
            "value_usd": 2.0,
            "volume": 20.0,
        },
    ]
    dataset_dir = (
        base_dir
        / "executions"
        / "data"
        / "fact_simulation"
        / "observation_date=20260507"
        / "run_mode=simulation"
        / "valuation_type=eod"
        / "valuation_year=2026"
        / "valuation_month=01"
    )
    dataset_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_parquet(dataset_dir / "data.parquet", index=False)


def _read_single_csv_from_zip(path):
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        assert len(names) == 1
        with archive.open(names[0]) as file:
            text = file.read().decode("utf-8")
    return list(csv.DictReader(text.splitlines()))


def test_filter_raw_data_export_contains_hive_partition_columns(tmp_path):
    _write_fact_simulation_dataset(tmp_path)
    service = RawDataExportService(_query_service(tmp_path))

    export_file = service.export_simulation_filters(
        run_mode="simulation",
        valuation_type="eod",
        observation_date=dt.date(2026, 5, 7),
        period_start=dt.date(2026, 1, 1),
        period_end=dt.date(2026, 1, 31),
        period_mode="valuations",
        gl_accounts=["OP_REV_SALES"],
        markets=["sales_fabr"],
        products=["pipelinegas"],
        dynamic_filters={"scenario": "base"},
    )

    rows = _read_single_csv_from_zip(export_file.path)
    export_file.path.unlink(missing_ok=True)

    assert export_file.filename == (
        "simulation_analysis_raw_data_2026-05-07_eod_scenario-base_valuations.zip"
    )
    assert len(rows) == 2
    assert rows[0]["observation_date"] == "20260507"
    assert rows[0]["run_mode"] == "simulation"
    assert rows[0]["valuation_type"] == "eod"
    assert rows[0]["valuation_period"] == "2026-01-01"
    assert "valuation_year" not in rows[0]
    assert "valuation_month" not in rows[0]
    assert rows[0]["gl_account"] == "OP_REV_SALES"


def test_sql_raw_data_export_ignores_ui_limit(tmp_path):
    _write_fact_simulation_dataset(tmp_path)
    service = RawDataExportService(_query_service(tmp_path))
    s3_path = (
        f"{tmp_path}/executions/data/fact_simulation/"
        "observation_date=20260507/run_mode=simulation/valuation_type=eod/**/*.parquet"
    )
    limited_sql = build_wrapped_simulation_sql(
        sql="SELECT * FROM simulation_data ORDER BY sample_index",
        s3_path=s3_path,
        limit=1,
    )
    assert "LIMIT 2" in limited_sql

    export_file = service.export_sql_query(
        sql="SELECT * FROM simulation_data ORDER BY sample_index",
        s3_path=s3_path,
        observation_date="20260507",
    )

    rows = _read_single_csv_from_zip(export_file.path)
    export_file.path.unlink(missing_ok=True)

    assert len(rows) == 2
    assert [row["sample_index"] for row in rows] == ["0", "1"]


def test_balance_raw_data_export_contains_exact_derived_sample_values():
    service = RawDataExportService()

    export_file = service.export_balance_sample_values(
        values=[30.0, 10.0, 20.0],
        observation_date=dt.date(2026, 5, 7),
        valuation_type="eod",
        balance_tree_slug="cash-flow",
        scenario="base",
    )

    rows = _read_single_csv_from_zip(export_file.path)
    export_file.path.unlink(missing_ok=True)

    assert export_file.filename == (
        "simulation_analysis_raw_data_2026-05-07_eod_tree-cash-flow_" "scenario-base_balance.zip"
    )
    assert rows == [
        {"sample_index": "0", "value_rub": "30.0"},
        {"sample_index": "1", "value_rub": "10.0"},
        {"sample_index": "2", "value_rub": "20.0"},
    ]


def test_balance_raw_data_endpoint_exports_physical_rows(monkeypatch):
    from api.valuation import results as results_api
    from domains.reporting.models.simulation_analysis import (
        PhysicalRowsResult,
        PhysicalSimulationRow,
        QueryDiagnostics,
        SourceMetadata,
    )

    columns = (
        "observation_date",
        "run_mode",
        "valuation_type",
        "valuation_year",
        "valuation_month",
        "gl_account",
        "market",
        "product",
        "scenario",
        "sample_index",
        "supply_path",
        "legal_entity",
        "payment_year",
        "payment_month",
        "value_usd",
        "value_rub",
        "volume",
    )
    row = PhysicalSimulationRow(
        observation_date=dt.date(2026, 5, 7),
        run_mode="simulation",
        valuation_type="eod",
        valuation_year=2026,
        valuation_month=1,
        gl_account="OP_REV_SALES",
        market="sales_fabr",
        product="pipelinegas",
        scenario="base",
        sample_index=0,
        supply_path=None,
        legal_entity=None,
        payment_year=2026,
        payment_month=1,
        value_usd=1.0,
        value_rub=100.0,
        volume=10.0,
    )
    result = PhysicalRowsResult(
        rows=(row,),
        columns=columns,
        diagnostics=QueryDiagnostics("SELECT physical", SourceMetadata(True, False), 1),
    )
    monkeypatch.setattr(results_api, "_query_simulation_analysis", lambda query: result)

    response = results_api.export_simulation_raw_data(
        period_start=dt.date(2026, 1, 1),
        period_end=dt.date(2026, 12, 31),
        observation_date=dt.date(2026, 5, 7),
        period_mode="payments",
        target="value_rub",
        gl_accounts=None,
        markets=None,
        products=None,
        filters='{"scenario":"base"}',
        run_mode="simulation",
        valuation_type="eod",
        source_mode="balance",
        balance_tree_slug="cash-flow",
    )

    rows = _read_single_csv_from_zip(response.path)
    response.path.unlink(missing_ok=True)

    assert rows[0]["sample_index"] == "0"
    assert rows[0]["value_rub"] == "100.0"
    assert rows[0]["gl_account"] == "OP_REV_SALES"


def _query_service(tmp_path) -> SimulationQueryService:
    base_path = StorageFS(LocalBackend()).path(
        str(tmp_path / "executions" / "data" / "fact_simulation")
    )
    return SimulationQueryService(DuckDbStorageAdapter(base_path))
