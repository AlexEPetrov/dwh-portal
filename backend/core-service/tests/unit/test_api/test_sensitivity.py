import json
from unittest.mock import Mock, patch
from uuid import UUID

import pandas as pd
import pytest
from fastapi import HTTPException

import infrastructure.files.filestore_registry as filestore_registry
from api.valuation.sensitivity import (
    ScenarioAnalysisRequest,
    ScenarioFactorShock,
    calculate_scenario_analysis,
    get_filter_presets,
)
from domains.reporting.services.simulation_query_service import SimulationQueryService
from domains.risk.services.scenario_analysis import (
    ScenarioAnalysisArrayContext,
    ScenarioAnalysisFilters,
    ScenarioAnalysisService,
)
from infrastructure.analytics.duckdb_storage_adapter import DuckDbStorageAdapter
from infrastructure.files.filestore_registry import get_file_store_registry


def test_scenario_analysis_uses_metadata_resolved_source_for_factors():
    metadata_service = Mock()
    metadata = Mock()
    metadata_base_path = Mock()
    metadata_service.load.return_value = metadata
    metadata_service.resolved_source_path.return_value = metadata_base_path

    filters = ScenarioAnalysisFilters(
        markets=["sales_fabr"],
        products=["pipelinegas"],
        supply_paths=[],
        gl_accounts=["OP_REV_SALES"],
        period_mode="valuations",
        currency="rub",
        valuation_type="eod",
        period_from=pd.Timestamp("2026-01-01").date(),
        period_to=pd.Timestamp("2026-12-31").date(),
        observation_date=pd.Timestamp("2026-05-07").date(),
        operation_id="moving-alias",
    )

    with patch.object(
        ScenarioAnalysisService,
        "_load_simulation_data",
        return_value=pd.DataFrame({"sample_index": [0], "revenue": [100.0]}),
    ), patch.object(
        ScenarioAnalysisService,
        "_load_factor_dataframe",
        return_value=pd.DataFrame({"sample_index": [0], "brent": [70.0]}),
    ) as load_factor, patch(
        "domains.risk.services.scenario_analysis.SimulationRunMetadataService",
        return_value=metadata_service,
    ):
        result = ScenarioAnalysisService._load_scenario_analysis_data(filters, ["brent"])

    assert result["brent"].tolist() == [70.0]
    load_factor.assert_called_once()
    assert load_factor.call_args.args[-1] is metadata_base_path


def _write_simulation_csv(path):
    rows = []
    for sample_index in range(12):
        rows.append(
            {
                "sample_index": sample_index,
                "valuation_period": "2026-01-01",
                "market": "sales_fabr",
                "product": "pipelinegas",
                "gl_account": "OP_REV_SALES",
                "value_rub": 1_000_000 + sample_index * 50_000,
            }
        )
        rows.append(
            {
                "sample_index": sample_index,
                "valuation_period": "2026-01-01",
                "market": "industrial",
                "product": "lng",
                "gl_account": "OP_TAX_DUTY",
                "value_rub": 500_000 + sample_index * 10_000,
            }
        )
        rows.append(
            {
                "sample_index": sample_index,
                "valuation_period": "2027-01-01",
                "market": "sales_fabr",
                "product": "pipelinegas",
                "gl_account": "OP_REV_SALES",
                "value_rub": 1_500_000 + sample_index * 50_000,
            }
        )
    pd.DataFrame(rows).to_csv(path, index=False)


def _write_simulation_parquet_dataset(base_dir):
    rows_20260507_202601 = []
    rows_20260507_202701 = []
    rows_20260428_202601 = []

    for sample_index in range(12):
        rows_20260507_202601.append(
            {
                "sample_index": sample_index,
                "scenario": "base",
                "market": "sales_fabr",
                "supply_path": "stream_a",
                "product": "pipelinegas",
                "gl_account": "OP_REV_SALES",
                "legal_entity": "entity_a",
                "payment_period": "2026-01",
                "valuation_period": "2026-01-01",
                "value_usd": 1000 + sample_index,
                "value_rub": 1_000_000 + sample_index * 50_000,
                "volume": 10 + sample_index,
            }
        )
        rows_20260507_202601.append(
            {
                "sample_index": sample_index,
                "scenario": "base",
                "market": "industrial",
                "supply_path": "stream_b",
                "product": "lng",
                "gl_account": "OP_TAX_DUTY",
                "legal_entity": "entity_b",
                "payment_period": "2026-01",
                "valuation_period": "2026-01-01",
                "value_usd": 500 + sample_index,
                "value_rub": 500_000 + sample_index * 10_000,
                "volume": 3 + sample_index,
            }
        )
        rows_20260507_202701.append(
            {
                "sample_index": sample_index,
                "scenario": "base",
                "market": "sales_fabr",
                "supply_path": "stream_a",
                "product": "pipelinegas",
                "gl_account": "OP_REV_SALES",
                "legal_entity": "entity_a",
                "payment_period": "2027-01",
                "valuation_period": "2027-01-01",
                "value_usd": 1500 + sample_index,
                "value_rub": 1_500_000 + sample_index * 50_000,
                "volume": 20 + sample_index,
            }
        )

        rows_20260428_202601.append(
            {
                "sample_index": sample_index,
                "scenario": "base",
                "market": "sales_fabr",
                "supply_path": "stream_a",
                "product": "pipelinegas",
                "gl_account": "OP_REV_SALES",
                "legal_entity": "entity_a",
                "payment_period": "2026-01",
                "valuation_period": "2026-01-01",
                "value_usd": 900 + sample_index,
                "value_rub": 900_000 + sample_index * 25_000,
                "volume": 8 + sample_index,
            }
        )

    datasets = [
        ("20260507", "2026", "01", rows_20260507_202601),
        ("20260507", "2027", "01", rows_20260507_202701),
        ("20260428", "2026", "01", rows_20260428_202601),
    ]

    for observation_date, valuation_year, valuation_month, rows in datasets:
        dataset_dir = (
            base_dir
            / "executions"
            / "data"
            / "fact_simulation"
            / f"observation_date={observation_date}"
            / "run_mode=simulation"
            / "valuation_type=eod"
            / f"valuation_year={valuation_year}"
            / f"valuation_month={valuation_month}"
        )
        dataset_dir.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(rows).to_parquet(dataset_dir / "data.parquet", index=False)


def _write_factor_csv(path, column_name: str, base_value: float, step: float):
    rows = []
    for sample_index in range(12):
        rows.append(
            {
                "sample_index": sample_index,
                column_name: base_value + sample_index * step,
            }
        )
    pd.DataFrame(rows).to_csv(path, index=False)


def _write_factor_parquet(path, base_value: float, step: float):
    rows = []
    for date_value, date_shift in [
        ("2026-01-01", 0.0),
        ("2026-06-01", 5.0),
        ("2026-12-31", 8.0),
        ("2027-01-01", 10.0),
    ]:
        row = {"date": date_value}
        for sample_index in range(12):
            row[f"sample_{sample_index}"] = base_value + sample_index * step + date_shift
        rows.append(row)
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_parquet(path, index=False)


def _prepare_csv_environment(tmp_path, monkeypatch):
    filestore_registry._file_store_registry_instance = None
    simulation_path = tmp_path / "data.csv"
    _write_simulation_csv(simulation_path)
    _write_simulation_parquet_dataset(tmp_path)
    _write_factor_csv(tmp_path / "brent_avg.csv", "brent_avg", 70.0, 1.5)
    _write_factor_csv(tmp_path / "ttf_avg.csv", "ttf_avg", 35.0, 0.8)
    _write_factor_csv(tmp_path / "usdrub_avg.csv", "usdrub_avg", 80.0, 0.6)
    monkeypatch.setenv("SIMULATION_CSV_PATH", str(simulation_path))
    monkeypatch.setenv("QUOTES_CSV_DIR", str(tmp_path))
    monkeypatch.setenv("APP_LOC_LOAD_FILES_PATH", str(tmp_path / "load_files"))
    monkeypatch.setenv("APP_LOC_ARCHIVE_PATH", str(tmp_path / "archive"))
    monkeypatch.setenv("APP_LOC_TEMP_PATH", str(tmp_path / "tmp"))
    monkeypatch.setenv("APP_LOC_REPOSITORY_PATH", str(tmp_path / "repository"))
    monkeypatch.setenv("APP_LOC_EXECUTION_PRESETS_PATH", str(tmp_path / "execution_presets"))
    monkeypatch.setenv("APP_LOC_SIMULATION_SOURCE_ROOT", str(tmp_path / "simulation_source"))
    monkeypatch.setenv("APP_LOC_SIMULATION_SOURCE_PATH", "")
    monkeypatch.setenv("APP_LOC_SIMULATION_TARGET_ROOT", str(tmp_path))
    monkeypatch.setenv("APP_LOC_SIMULATION_TARGET_PATH", "")
    monkeypatch.setenv("APP_LOC_SIMULATION_HIVE_PATH", "hive_results")
    monkeypatch.setenv("APP_LOC_VALUATION_TARGET_ROOT", str(tmp_path / "valuation"))
    monkeypatch.setenv("APP_LOC_VALUATION_TARGET_PATH", "")
    monkeypatch.setenv("APP_LOC_STORAGE_ROOT", str(tmp_path))
    monkeypatch.setenv("APP_LOC_BALANCE_DATA_ROOT", str(tmp_path / "balance_data"))

    source_root = tmp_path / "simulation_source"
    _write_factor_parquet(source_root / "BRENT_DATED.parquet", 70.0, 1.5)
    _write_factor_parquet(source_root / "TTF_MA.parquet", 35.0, 0.8)
    _write_factor_parquet(source_root / "CBR_USD_RUB.parquet", 80.0, 0.6)


def _prepare_operation_id_quote_environment(tmp_path, monkeypatch, operation_id: UUID):
    _prepare_csv_environment(tmp_path, monkeypatch)
    monkeypatch.setenv(
        "APP_LOC_SIMULATION_SOURCE_PATH",
        "mcmf/observation_date={observation_date}/operation_id={operation_id}",
    )
    actual_source_dir = (
        tmp_path
        / "simulation_source"
        / "mcmf"
        / "observation_date=20260430"
        / f"operation_id={operation_id}"
    )
    _write_factor_parquet(actual_source_dir / "BRENT_DATED.parquet", 70.0, 1.5)
    _write_factor_parquet(actual_source_dir / "TTF_MA.parquet", 35.0, 0.8)
    _write_factor_parquet(actual_source_dir / "CBR_USD_RUB.parquet", 80.0, 0.6)


def _prepare_nearest_left_quote_environment(tmp_path, monkeypatch):
    _prepare_csv_environment(tmp_path, monkeypatch)
    monkeypatch.setenv(
        "APP_LOC_SIMULATION_SOURCE_PATH",
        "mcmf/observation_date={observation_date}/operation_id={operation_id}",
    )
    stale_operation_id = UUID("018f2b34-1234-7abc-8def-123456789aaa")
    latest_operation_id = UUID("018f2b34-1234-7abc-8def-123456789bbb")
    future_operation_id = UUID("018f2b34-1234-7abc-8def-123456789ccc")

    stale_dir = (
        tmp_path
        / "simulation_source"
        / "mcmf"
        / "observation_date=20260428"
        / f"operation_id={stale_operation_id}"
    )
    latest_dir = (
        tmp_path
        / "simulation_source"
        / "mcmf"
        / "observation_date=20260430"
        / f"operation_id={latest_operation_id}"
    )
    future_dir = (
        tmp_path
        / "simulation_source"
        / "mcmf"
        / "observation_date=20260508"
        / f"operation_id={future_operation_id}"
    )
    _write_factor_parquet(stale_dir / "BRENT_DATED.parquet", 50.0, 1.5)
    _write_factor_parquet(latest_dir / "BRENT_DATED.parquet", 70.0, 1.5)
    _write_factor_parquet(future_dir / "BRENT_DATED.parquet", 500.0, 1.5)
    for quote_name in ["TTF_MA", "CBR_USD_RUB"]:
        _write_factor_parquet(stale_dir / f"{quote_name}.parquet", 35.0, 0.8)
        _write_factor_parquet(latest_dir / f"{quote_name}.parquet", 35.0, 0.8)
        _write_factor_parquet(future_dir / f"{quote_name}.parquet", 35.0, 0.8)


def test_scenario_analysis_uses_canonical_simulation_query_service(tmp_path, monkeypatch):
    _prepare_csv_environment(tmp_path, monkeypatch)

    filters = ScenarioAnalysisFilters(
        markets=["sales_fabr"],
        products=["pipelinegas"],
        supply_paths=[],
        gl_accounts=["OP_REV_SALES"],
        period_mode="valuations",
        currency="rub",
        valuation_type="eod",
        period_from=pd.Timestamp("2026-01-01").date(),
        period_to=pd.Timestamp("2026-01-01").date(),
        observation_date=pd.Timestamp("2026-05-07").date(),
        scenario="base",
    )

    scenario_df = ScenarioAnalysisService._load_simulation_data(filters)
    registry = get_file_store_registry()
    canonical_df = SimulationQueryService(
        DuckDbStorageAdapter(registry.executions_data_root() / "fact_simulation")
    ).query_sample_target_dataframe(
        run_mode="simulation",
        valuation_type="eod",
        observation_date=pd.Timestamp("2026-05-07").date(),
        period_start=pd.Timestamp("2026-01-01").date(),
        period_end=pd.Timestamp("2026-01-01").date(),
        period_mode="valuations",
        target="value_rub",
        target_alias="revenue",
        gl_accounts=["OP_REV_SALES"],
        markets=["sales_fabr"],
        products=["pipelinegas"],
        dynamic_filters={"scenario": "base"},
    )

    pd.testing.assert_frame_equal(
        scenario_df.reset_index(drop=True),
        canonical_df.reset_index(drop=True),
    )


def test_scenario_analysis_applies_supply_path_filter(tmp_path, monkeypatch):
    _prepare_csv_environment(tmp_path, monkeypatch)

    filters = ScenarioAnalysisFilters(
        markets=[],
        products=[],
        supply_paths=["stream_b"],
        gl_accounts=[],
        period_mode="valuations",
        currency="rub",
        valuation_type="eod",
        period_from=pd.Timestamp("2026-01-01").date(),
        period_to=pd.Timestamp("2026-01-01").date(),
        observation_date=pd.Timestamp("2026-05-07").date(),
        scenario="base",
    )

    result = ScenarioAnalysisService._load_simulation_data(filters)

    assert result["sample_index"].nunique() == 12
    assert result["revenue"].min() >= 500_000
    assert result["revenue"].max() < 1_000_000


def test_calculate_scenario_analysis_returns_plot_ready_series(tmp_path, monkeypatch):
    _prepare_csv_environment(tmp_path, monkeypatch)

    response = calculate_scenario_analysis(
        ScenarioAnalysisRequest(
            markets=["sales_fabr"],
            products=["pipelinegas"],
            gl_accounts=["OP_REV_SALES"],
            period_mode="valuations",
            period_from="2026-01-01",
            period_to="2027-01-01",
            observation_date="2026-05-07",
            shocks=[
                ScenarioFactorShock(name="brent", shift_percent=10.0),
                ScenarioFactorShock(name="ttf", shift_percent=10.0),
                ScenarioFactorShock(name="usdrub", shift_percent=10.0),
            ],
            n_bootstrap=300,
            random_seed=7,
            include_values=True,
        )
    )

    scenario_names = [scenario.name for scenario in response.scenarios]
    assert scenario_names[0] == "Исходное"
    assert "Только Brent" in scenario_names
    assert "Только TTF" in scenario_names
    assert "Только курс" in scenario_names
    assert "Совместный (корреляции сохранены)" in scenario_names
    assert "Все факторы + полный разрыв" in scenario_names
    assert response.base_scenario == "Исходное"
    assert [shock.name for shock in response.applied_shocks] == ["brent", "ttf", "usdrub"]
    assert "scenario_diagnostics" in response.diagnostics
    assert "scenario_confidence" in response.diagnostics
    assert response.diagnostics["scenario_diagnostics"]["Исходное"]["confidence"]["status"] in {
        "RELIABLE",
        "LIMITED",
        "UNRELIABLE",
    }
    assert "weight_health" in response.diagnostics["scenario_diagnostics"]["Исходное"]
    assert "target_fidelity" in response.diagnostics["scenario_diagnostics"]["Только Brent"]
    assert all(len(series.values) > 0 for series in response.scenarios)
    assert all(len(series.density.x_grid) == 500 for series in response.scenarios)
    assert response.scenarios[0].business_case == "Базовое распределение"
    assert next(
        scenario.business_case for scenario in response.scenarios if scenario.name == "Только Brent"
    ).startswith("Нефтяной шок: Brent +10%")
    assert response.diagnostics["execution"]["shock_scope"] == "forecast_period"
    assert response.diagnostics["preparation"]["shock_scope"] == "forecast_period"
    assert response.diagnostics["preparation"]["factor_window"] == {
        "observation_date": "2026-05-07",
        "period_from": "2026-05-08",
        "period_to": "2027-01-31",
        "forecast_start_rule": "date > observation_date",
    }


def test_scenario_analysis_rejects_filters_with_revenue_array():
    filters = ScenarioAnalysisFilters(
        markets=[],
        products=[],
        supply_paths=[],
        gl_accounts=[],
        period_mode="payments",
        currency="rub",
        valuation_type="eod",
        period_from=pd.Timestamp("2026-01-01").date(),
        period_to=pd.Timestamp("2026-12-31").date(),
        observation_date=pd.Timestamp("2026-05-07").date(),
    )
    array_context = ScenarioAnalysisArrayContext(
        observation_date=pd.Timestamp("2026-05-07").date(),
        period_from=pd.Timestamp("2026-01-01").date(),
        period_to=pd.Timestamp("2026-12-31").date(),
    )

    with pytest.raises(ValueError, match="Specify exactly one source"):
        ScenarioAnalysisService.prepare(
            filters=filters,
            revenue_array=pd.Series([1.0, 2.0]).to_numpy(),
            array_context=array_context,
        )


def test_scenario_analysis_requires_array_context_with_revenue_array():
    with pytest.raises(ValueError, match="array_context is required"):
        ScenarioAnalysisService.prepare(
            revenue_array=pd.Series([1.0, 2.0]).to_numpy(),
        )


def test_scenario_analysis_array_context_is_single_balance_source(monkeypatch):
    calls = []

    def fake_load_factor_dataframe(
        *,
        factor_name,
        observation_date,
        period_from,
        period_to,
        operation_id=None,
        metadata_base_path=None,
    ):
        calls.append(
            {
                "factor_name": factor_name,
                "observation_date": observation_date,
                "period_from": period_from,
                "period_to": period_to,
                "operation_id": operation_id,
                "metadata_base_path": metadata_base_path,
            }
        )
        return pd.DataFrame({"sample_index": [0, 1], factor_name: [10.0, 11.0]})

    monkeypatch.setattr(
        ScenarioAnalysisService,
        "_load_factor_dataframe",
        fake_load_factor_dataframe,
    )

    prepared = ScenarioAnalysisService.prepare(
        revenue_array=pd.Series([100.0, 200.0]).to_numpy(),
        array_context=ScenarioAnalysisArrayContext(
            observation_date=pd.Timestamp("2026-05-07").date(),
            period_from=pd.Timestamp("2026-01-15").date(),
            period_to=pd.Timestamp("2026-12-01").date(),
            operation_id="stress-run",
            scenario="base",
        ),
        factor_names=["brent"],
        shock_scope="forecast_period",
    )

    assert prepared.filtered_scenario == "base"
    assert prepared.preparation_diagnostics["factor_window"] == {
        "observation_date": "2026-05-07",
        "period_from": "2026-05-08",
        "period_to": "2026-12-31",
        "forecast_start_rule": "date > observation_date",
    }
    assert calls == [
        {
            "factor_name": "brent",
            "observation_date": pd.Timestamp("2026-05-07").date(),
            "period_from": pd.Timestamp("2026-05-08").date(),
            "period_to": pd.Timestamp("2026-12-31").date(),
            "operation_id": "stress-run",
            "metadata_base_path": None,
        }
    ]


def test_calculate_scenario_analysis_supports_full_selected_period_shock_scope(
    tmp_path, monkeypatch
):
    _prepare_csv_environment(tmp_path, monkeypatch)

    response = calculate_scenario_analysis(
        ScenarioAnalysisRequest(
            markets=["sales_fabr"],
            products=["pipelinegas"],
            gl_accounts=["OP_REV_SALES"],
            period_mode="valuations",
            period_from="2026-01-01",
            period_to="2026-12-31",
            observation_date="2026-05-07",
            shock_scope="full_selected_period",
            shocks=[ScenarioFactorShock(name="brent", shift_percent=10.0)],
            n_bootstrap=300,
            random_seed=7,
        )
    )

    assert response.diagnostics["execution"]["shock_scope"] == "full_selected_period"
    assert response.diagnostics["preparation"]["shock_scope"] == "full_selected_period"
    assert response.diagnostics["preparation"]["factor_window"] == {
        "observation_date": "2026-05-07",
        "period_from": "2026-01-01",
        "period_to": "2026-12-31",
        "forecast_start_rule": None,
    }


def test_calculate_scenario_analysis_ignores_zero_shocks(tmp_path, monkeypatch):
    _prepare_csv_environment(tmp_path, monkeypatch)

    response = calculate_scenario_analysis(
        ScenarioAnalysisRequest(
            markets=["sales_fabr"],
            products=["pipelinegas"],
            gl_accounts=["OP_REV_SALES"],
            period_mode="valuations",
            period_from="2026-01-01",
            period_to="2026-12-31",
            observation_date="2026-05-07",
            shocks=[
                ScenarioFactorShock(name="brent", shift_percent=0.0),
                ScenarioFactorShock(name="ttf", shift_percent=0.0),
                ScenarioFactorShock(name="usdrub", shift_percent=0.0),
            ],
            n_bootstrap=300,
            random_seed=7,
        )
    )

    assert [scenario.name for scenario in response.scenarios] == ["Исходное"]
    assert response.applied_shocks == []


def test_calculate_scenario_analysis_rejects_unknown_factor():
    with pytest.raises(HTTPException) as exc_info:
        calculate_scenario_analysis(
            ScenarioAnalysisRequest(
                markets=["sales_fabr"],
                period_mode="valuations",
                period_from="2026-01-01",
                period_to="2027-01-01",
                observation_date="2026-05-07",
                shocks=[ScenarioFactorShock(name="power", shift_percent=10.0)],
            )
        )

    assert exc_info.value.status_code == 400
    assert "Unsupported scenario factor" in str(exc_info.value.detail)


def test_calculate_scenario_analysis_supports_multi_filters_and_year_range(tmp_path, monkeypatch):
    _prepare_csv_environment(tmp_path, monkeypatch)

    response = calculate_scenario_analysis(
        ScenarioAnalysisRequest(
            markets=["sales_fabr"],
            products=["pipelinegas"],
            gl_accounts=["OP_REV_SALES"],
            period_mode="valuations",
            period_from="2026-01-15",
            period_to="2027-01-31",
            observation_date="2026-05-07",
            shocks=[ScenarioFactorShock(name="brent", shift_percent=10.0)],
            n_bootstrap=300,
            random_seed=7,
            include_values=True,
        )
    )

    assert response.scenarios[0].name == "Исходное"
    assert len(response.scenarios[0].values) == 12
    assert response.scenarios[0].stats.mean > 2_000_000


def test_calculate_scenario_analysis_supports_usd_currency(tmp_path, monkeypatch):
    _prepare_csv_environment(tmp_path, monkeypatch)

    response = calculate_scenario_analysis(
        ScenarioAnalysisRequest(
            markets=["sales_fabr"],
            products=["pipelinegas"],
            gl_accounts=["OP_REV_SALES"],
            period_mode="valuations",
            currency="usd",
            period_from="2026-01-01",
            period_to="2026-12-31",
            observation_date="2026-05-07",
            shocks=[ScenarioFactorShock(name="brent", shift_percent=0.0)],
            n_bootstrap=300,
            random_seed=7,
        )
    )

    assert response.scenarios[0].name == "Исходное"
    assert response.scenarios[0].stats.mean < 2_000


def test_calculate_scenario_analysis_supports_payment_period_mode_and_observation_partition(
    tmp_path, monkeypatch
):
    _prepare_csv_environment(tmp_path, monkeypatch)

    response = calculate_scenario_analysis(
        ScenarioAnalysisRequest(
            markets=["sales_fabr"],
            products=["pipelinegas"],
            gl_accounts=["OP_REV_SALES"],
            period_mode="payments",
            period_from="2026-01-01",
            period_to="2026-12-31",
            observation_date="2026-04-28",
            shocks=[ScenarioFactorShock(name="brent", shift_percent=10.0)],
            n_bootstrap=300,
            random_seed=7,
            include_values=True,
        )
    )

    assert response.scenarios[0].name == "Исходное"
    assert len(response.scenarios[0].values) == 12
    assert response.scenarios[0].stats.mean < 1_200_000


def test_calculate_scenario_analysis_resolves_quote_by_operation_id_across_observation_partitions(
    tmp_path, monkeypatch
):
    operation_id = UUID("018f2b34-1234-7abc-8def-123456789abc")
    _prepare_operation_id_quote_environment(tmp_path, monkeypatch, operation_id)

    response = calculate_scenario_analysis(
        ScenarioAnalysisRequest(
            markets=["sales_fabr"],
            products=["pipelinegas"],
            gl_accounts=["OP_REV_SALES"],
            period_mode="valuations",
            period_from="2026-01-01",
            period_to="2026-12-31",
            observation_date="2026-05-07",
            operation_id=operation_id,
            shocks=[ScenarioFactorShock(name="brent", shift_percent=10.0)],
            n_bootstrap=300,
            random_seed=7,
            include_values=True,
        )
    )

    assert response.scenarios[0].name == "Исходное"
    assert len(response.scenarios[0].values) == 12
    assert "Только Brent" in [scenario.name for scenario in response.scenarios]


def test_calculate_scenario_analysis_resolves_quote_from_newest_mcmf_observation_not_after_selected(
    tmp_path, monkeypatch
):
    _prepare_nearest_left_quote_environment(tmp_path, monkeypatch)

    response = calculate_scenario_analysis(
        ScenarioAnalysisRequest(
            markets=["sales_fabr"],
            products=["pipelinegas"],
            gl_accounts=["OP_REV_SALES"],
            period_mode="valuations",
            period_from="2026-01-01",
            period_to="2027-01-01",
            observation_date="2026-05-07",
            shocks=[ScenarioFactorShock(name="brent", shift_percent=10.0)],
            n_bootstrap=300,
            random_seed=7,
            include_values=True,
        )
    )

    assert response.scenarios[0].name == "Исходное"
    assert len(response.scenarios[0].values) == 12
    assert "Только Brent" in [scenario.name for scenario in response.scenarios]


def test_get_filter_presets_returns_configured_collection(tmp_path, monkeypatch):
    presets_path = tmp_path / "valuation-filter-presets.json"
    presets_path.write_text(
        json.dumps(
            [
                {
                    "id": "industrial-payments-q1",
                    "name": "Industrial / Payments / Q1",
                    "description": "Mounted preset",
                    "filters": {
                        "markets": ["industrial"],
                        "products": ["lng"],
                        "supply_paths": ["north"],
                        "gl_accounts": ["OP_TAX_DUTY"],
                        "period_mode": "payments",
                        "period_from": "2026-01-01",
                        "period_to": "2026-03-31",
                        "observation_date": "2026-04-28",
                    },
                }
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("APP_LOC_FILTER_PRESETS_PATH", str(presets_path))

    response = get_filter_presets()

    assert len(response) == 1
    assert response[0].filters.period_mode == "payments"
    assert response[0].filters.supply_paths == ["north"]
    assert response[0].filters.observation_date.isoformat() == "2026-04-28"


def test_get_filter_presets_returns_empty_when_path_is_unset(monkeypatch):
    monkeypatch.delenv("APP_LOC_FILTER_PRESETS_PATH", raising=False)

    assert get_filter_presets() == []


def test_get_filter_presets_returns_empty_when_file_is_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_LOC_FILTER_PRESETS_PATH", str(tmp_path / "missing.json"))

    assert get_filter_presets() == []


@pytest.mark.parametrize(
    "content",
    [
        "{invalid json",
        json.dumps([{"id": "broken", "name": "Broken", "filters": {"unexpected": True}}]),
        json.dumps(
            [
                {
                    "id": "duplicate",
                    "name": "First",
                    "filters": {
                        "period_from": "2026-01-01",
                        "period_to": "2026-12-31",
                        "observation_date": "2026-04-28",
                    },
                },
                {
                    "id": "duplicate",
                    "name": "Second",
                    "filters": {
                        "period_from": "2026-01-01",
                        "period_to": "2026-12-31",
                        "observation_date": "2026-04-28",
                    },
                },
            ]
        ),
    ],
)
def test_get_filter_presets_reports_invalid_config(tmp_path, monkeypatch, content):
    presets_path = tmp_path / "valuation-filter-presets.json"
    presets_path.write_text(content, encoding="utf-8")
    monkeypatch.setenv("APP_LOC_FILTER_PRESETS_PATH", str(presets_path))

    with pytest.raises(HTTPException, match="Invalid valuation filter presets file") as exc_info:
        get_filter_presets()

    assert exc_info.value.status_code == 500
