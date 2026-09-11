"""Tests for ModelledPositionService."""

import datetime as dt
from unittest.mock import MagicMock

import pytest

from domains.risk.services.balance.cell import BalanceCellValue
from domains.risk.services.balance.sources.modelled_balance_cell_resolver import (
    ContractsFilter,
    ModelledPositionService,
)


class TestModelledPositionService:
    """Tests for ModelledPositionService.get_value()."""

    def test_resolve_constant_value(self):
        """Test resolving a constant value from internal://constant/<value> URI."""
        mock_sql_service = MagicMock()
        service = ModelledPositionService(query_service=mock_sql_service)
        result = service.get_value(dt.date(2026, 5, 8), "internal://constant/123.45")
        assert result == 123.45

    def test_resolve_constant_negative_value(self):
        """Test resolving a negative constant value."""
        mock_sql_service = MagicMock()
        service = ModelledPositionService(query_service=mock_sql_service)
        result = service.get_value(dt.date(2026, 5, 8), "internal://constant/-50.0")
        assert result == -50.0

    def test_resolve_constant_zero_value(self):
        """Test resolving a zero constant value."""
        mock_sql_service = MagicMock()
        service = ModelledPositionService(query_service=mock_sql_service)
        result = service.get_value(dt.date(2026, 5, 8), "internal://constant/0")
        assert result == 0.0

    def test_resolve_constant_invalid_value_raises(self):
        """Test that non-numeric constant values raise ValueError."""
        mock_sql_service = MagicMock()
        service = ModelledPositionService(query_service=mock_sql_service)
        with pytest.raises(ValueError, match="Constant value in URI must be numeric"):
            service.get_value(dt.date(2026, 5, 8), "internal://constant/abc")

    def test_resolve_constant_returns_report_value_for_calculated_tree_boundary(self):
        """Constants are user-entered values already expressed in report_currency."""
        service = ModelledPositionService(query_service=MagicMock())

        result = service.resolve_value(dt.date(2026, 5, 8), "const://2000000000")

        assert result.value == 2_000_000_000
        assert result.cell_source == "const"

    def test_resolve_contracts_median(self):
        """Test resolving contracts-based position returns median from simulation data."""
        mock_sql_service = MagicMock()
        mock_sql_service.execute_query.return_value = (
            ["median_value"],
            [[42.5 * 1_000_000_000]],
            10.0,
        )

        service = ModelledPositionService(query_service=mock_sql_service)
        result = service.get_value(
            dt.date(2026, 5, 8),
            "internal://contracts?gl_account=OP_TAX_DUTY",
        )

        assert result == 42.5 * 1_000_000_000
        mock_sql_service.execute_query.assert_called_once()
        call_args = mock_sql_service.execute_query.call_args
        assert call_args[1]["observation_date"] == "20260508"
        assert call_args[1]["run_mode"] == "simulation"
        assert "gl_account = 'OP_TAX_DUTY'" in call_args[0][0]

    def test_resolve_contracts_with_multiple_filters(self):
        """Test contracts URI with multiple filter parameters."""
        mock_sql_service = MagicMock()
        mock_sql_service.execute_query.return_value = (
            ["median_value"],
            [[100.0 * 1_000_000_000]],
            10.0,
        )

        service = ModelledPositionService(query_service=mock_sql_service)
        result = service.get_value(
            dt.date(2026, 5, 8),
            "internal://contracts?gl_account=GL_TAX_1&counterparty=OOO_Example&product=Gas",
        )

        assert result == 100.0 * 1_000_000_000
        call_args = mock_sql_service.execute_query.call_args
        sql = call_args[0][0]
        assert "gl_account = 'GL_TAX_1'" in sql
        assert "counterparty = 'OOO_Example'" in sql
        assert "product = 'Gas'" in sql

    def test_resolve_contracts_filters_by_scenario_when_provided(self):
        """Test that scenario is applied as an explicit simulation partition filter."""
        mock_sql_service = MagicMock()
        mock_sql_service.execute_query.return_value = (
            ["median_value"],
            [[100.0 * 1_000_000_000]],
            10.0,
        )

        service = ModelledPositionService(query_service=mock_sql_service)
        result = service.get_value(
            dt.date(2026, 5, 8),
            "internal://contracts?gl_account=GL_TAX_1",
            scenario="positive",
        )

        assert result == 100.0 * 1_000_000_000
        sql = mock_sql_service.execute_query.call_args[0][0]
        assert "scenario = 'positive'" in sql

    def test_resolve_contracts_avg_uses_average_reducer(self):
        """Test that avg reducer uses per-sample average instead of median."""
        mock_sql_service = MagicMock()
        mock_sql_service.execute_query.return_value = (
            ["reduced_sample_value"],
            [[75.0 * 1_000_000_000]],
            10.0,
        )

        service = ModelledPositionService(query_service=mock_sql_service)
        result = service.get_value(
            dt.date(2026, 5, 8),
            "internal://contracts?gl_account=GL_TAX_1",
            reducer="avg",
        )

        assert result == 75.0 * 1_000_000_000
        sql = mock_sql_service.execute_query.call_args[0][0]
        assert "avg(sample_value) AS reduced_sample_value" in sql
        assert "quantile_cont(sample_value, 0.5)" not in sql

    def test_resolve_contracts_rejects_unknown_reducer(self):
        """Unsupported simulation reducers fail before SQL execution."""
        mock_sql_service = MagicMock()
        service = ModelledPositionService(query_service=mock_sql_service)

        with pytest.raises(ValueError, match="Unsupported modelled position reducer"):
            service.get_value(
                dt.date(2026, 5, 8),
                "internal://contracts?gl_account=GL_TAX_1",
                reducer="p95",  # type: ignore[arg-type]
            )

        mock_sql_service.execute_query.assert_not_called()

    def test_resolve_contracts_empty_filter_raises(self):
        """Test that contracts URI without any filter raises ValueError."""
        mock_sql_service = MagicMock()
        service = ModelledPositionService(query_service=mock_sql_service)
        with pytest.raises(ValueError, match="must contain at least one filter parameter"):
            service.get_value(dt.date(2026, 5, 8), "internal://contracts")

    def test_resolve_contract_det_uses_prepared_scope_and_sums_pnl_rows(self):
        """Test that contract://...?mode=det uses Rust prepared-scope deterministic PnL."""
        mock_sql_service = MagicMock()
        scope_service = MagicMock()
        scope_service.prepare.return_value = {"snapshot_id": "snapshot-1"}
        scope_service.calculate_contract_pnl.return_value = {
            "results": [{"value": 10.0}, {"value": None}, {"value": 2.5}]
        }

        service = ModelledPositionService(
            query_service=mock_sql_service,
            deterministic_scope_service=scope_service,
        )
        service.prepare_deterministic_snapshot(
            dt.date(2026, 5, 8),
            2026,
            "base",
            ["contract1"],
        )
        result = service.resolve_value(
            dt.date(2026, 5, 8),
            "contract://?slug=contract1&mode=det",
            balance_year=2026,
        )

        assert result.value == 12.5
        assert result.cell_source == "contract"
        assert result.scenario_mode == "deterministic"
        scope_service.prepare.assert_called_once()
        prepared_command = scope_service.prepare.call_args.args[0]
        assert prepared_command.observation_date == dt.date(2026, 5, 8)
        assert prepared_command.valuation_start_date == dt.date(2026, 1, 1)
        assert prepared_command.valuation_end_date == dt.date(2026, 12, 31)
        scope_service.calculate_contract_pnl.assert_called_once_with(
            snapshot_id="snapshot-1",
            contract_id="contract1",
            valuation_start_date=dt.date(2026, 1, 1),
            valuation_end_date=dt.date(2026, 12, 31),
        )

    def test_resolve_contract_without_det_keeps_simulation_path(self):
        """Test that contract:// without mode=det still reads existing simulation results."""
        mock_sql_service = MagicMock()
        mock_sql_service.execute_query.return_value = (
            ["median_value"],
            [[42.0 * 1_000_000_000]],
            10.0,
        )
        scope_service = MagicMock()

        service = ModelledPositionService(
            query_service=mock_sql_service,
            deterministic_scope_service=scope_service,
        )
        result = service.resolve_value(dt.date(2026, 5, 8), "contract://?slug=contract1")

        assert result.value == 42.0 * 1_000_000_000
        assert result.cell_source == "contract"
        assert result.scenario_mode == "simulation"
        scope_service.prepare.assert_not_called()

    def test_resolve_contract_mode_curve_uses_simulation_path(self):
        """contract://...?mode=curve is an explicit alias for simulation-path modelled values."""
        mock_sql_service = MagicMock()
        mock_sql_service.execute_query.return_value = (
            ["median_value"],
            [[42.0 * 1_000_000_000]],
            10.0,
        )

        service = ModelledPositionService(query_service=mock_sql_service)
        result = service.resolve_value(
            dt.date(2026, 5, 8),
            "contract://?slug=contract1&mode=curve",
        )

        assert result.value == 42.0 * 1_000_000_000
        assert result.cell_source == "contract"
        assert result.scenario_mode == "simulation"

    def test_resolve_dataset_uses_shared_monitored_resolver(self):
        """dataset:// modelled cells reuse the same dataset semantics as baseline cells."""
        mock_sql_service = MagicMock()
        monitored_service = MagicMock()
        monitored_service.resolve_value.return_value = BalanceCellValue(
            12.5, "dataset", "deterministic"
        )

        service = ModelledPositionService(
            query_service=mock_sql_service,
            monitored_position_service=monitored_service,
        )
        result = service.resolve_value(
            dt.date(2026, 5, 8),
            "dataset://MONITORED_DATA?page_title=Balance%20Sheet",
            balance_year=2026,
            scenario="base",
        )

        assert result == BalanceCellValue(12.5, "dataset", "deterministic")
        monitored_service.resolve_value.assert_called_once_with(
            dt.date(2026, 5, 8),
            "dataset://MONITORED_DATA?page_title=Balance%20Sheet",
            2026,
            "base",
        )

    def test_curve_uri_is_explicit_stub(self):
        """curve:// scalar modelled cells stay unsupported until curve scalar policy is documented."""
        mock_sql_service = MagicMock()
        service = ModelledPositionService(query_service=mock_sql_service)

        with pytest.raises(NotImplementedError, match="explicit scalar curve policy"):
            service.resolve_value(dt.date(2026, 5, 8), "curve://TTF_FORWARD")

    def test_resolve_contracts_no_data_returns_zero(self):
        """Test that get_value keeps legacy zero fallback when no simulation data matches."""
        mock_sql_service = MagicMock()
        mock_sql_service.execute_query.return_value = (
            ["median_value"],
            [[None]],
            10.0,
        )

        service = ModelledPositionService(query_service=mock_sql_service)
        result = service.get_value(
            dt.date(2026, 5, 8),
            "internal://contracts?gl_account=NONEXISTENT",
        )

        assert result == 0.0

    def test_resolve_value_reports_missing_simulation_data(self):
        """Test that resolve_value distinguishes missing simulation data from real zero values."""
        mock_sql_service = MagicMock()
        mock_sql_service.execute_query.return_value = (
            ["median_value"],
            [[None]],
            10.0,
        )

        service = ModelledPositionService(query_service=mock_sql_service)
        result = service.resolve_value(
            dt.date(2026, 5, 8),
            "internal://contracts?gl_account=NONEXISTENT",
        )

        assert result.value is None
        assert result.cell_source == "contract"
        assert result.scenario_mode == "simulation"

    def test_resolve_contracts_empty_rows_returns_zero(self):
        """Test that when query returns no rows, median returns 0.0."""
        mock_sql_service = MagicMock()
        mock_sql_service.execute_query.return_value = (
            ["median_value"],
            [],
            10.0,
        )

        service = ModelledPositionService(query_service=mock_sql_service)
        result = service.get_value(
            dt.date(2026, 5, 8),
            "internal://contracts?gl_account=NONEXISTENT",
        )

        assert result == 0.0

    def test_unrecognized_uri_format_raises(self):
        """Test that unrecognized URI formats raise ValueError."""
        mock_sql_service = MagicMock()
        service = ModelledPositionService(query_service=mock_sql_service)
        with pytest.raises(ValueError, match="Unrecognized modelled_position URI format"):
            service.get_value(dt.date(2026, 5, 8), "internal://unknown/something")

    def test_sql_error_propagates(self):
        """Test that SQL execution errors are wrapped in RuntimeError."""
        mock_sql_service = MagicMock()
        mock_sql_service.execute_query.side_effect = Exception("DuckDB connection failed")

        service = ModelledPositionService(query_service=mock_sql_service)
        with pytest.raises(RuntimeError, match="Failed to compute median"):
            service.get_value(
                dt.date(2026, 5, 8),
                "internal://contracts?gl_account=OP_TAX_DUTY",
            )

    def test_missing_simulation_partition_reports_missing_value(self):
        """Missing valuation_type/run_mode partitions should behave like no simulation data."""
        mock_sql_service = MagicMock()
        mock_sql_service.execute_query.side_effect = RuntimeError(
            "DuckDB query execution failed: IO Error: No files found that match the pattern"
        )

        service = ModelledPositionService(query_service=mock_sql_service)
        result = service.resolve_value(
            dt.date(2026, 5, 8),
            "internal://contracts?gl_account=OP_TAX_DUTY",
        )

        assert result.value is None
        assert result.cell_source == "contract"
        assert result.scenario_mode == "simulation"


class TestContractsFilter:
    """Tests for ContractsFilter dataclass."""

    def test_is_empty_when_no_filters(self):
        """Test is_empty returns True when no filters are set."""
        filter_params = ContractsFilter()
        assert filter_params.is_empty() is True

    def test_is_not_empty_with_gl_account(self):
        """Test is_empty returns False when gl_account is set."""
        filter_params = ContractsFilter(gl_account="GL_TAX_1")
        assert filter_params.is_empty() is False

    def test_simulation_array_uses_simulation_run_mode(self):
        """Test full simulation arrays are read from simulation run_mode partitions."""
        mock_sql_service = MagicMock()
        mock_sql_service.execute_query.return_value = (
            ["sample_index", "sample_value"],
            [[0, 1_000_000], [1, 2_000_000]],
            10.0,
        )

        service = ModelledPositionService(query_service=mock_sql_service)
        result = service.get_simulation_array(
            dt.date(2026, 5, 8),
            "internal://contracts?gl_account=OP_TAX_DUTY",
        )

        assert result.tolist() == [1.0, 2.0]
        call_args = mock_sql_service.execute_query.call_args
        assert call_args[1]["run_mode"] == "simulation"

    def test_simulation_array_filters_by_scenario_when_provided(self):
        """Test full simulation arrays apply the selected scenario partition filter."""
        mock_sql_service = MagicMock()
        mock_sql_service.execute_query.return_value = (
            ["sample_index", "sample_value"],
            [[0, 1_000_000]],
            10.0,
        )

        service = ModelledPositionService(query_service=mock_sql_service)
        result = service.get_simulation_array(
            dt.date(2026, 5, 8),
            "internal://contracts?gl_account=OP_TAX_DUTY",
            scenario="negative",
        )

        assert result.tolist() == [1.0]
        sql = mock_sql_service.execute_query.call_args[0][0]
        assert "scenario = 'negative'" in sql

    def test_is_not_empty_with_slug(self):
        """Test is_empty returns False when slug is set."""
        filter_params = ContractsFilter(slug="CONTRACT_001")
        assert filter_params.is_empty() is False

    def test_is_not_empty_with_counterparty(self):
        """Test is_empty returns False when counterparty is set."""
        filter_params = ContractsFilter(counterparty="OOO_Example")
        assert filter_params.is_empty() is False

    def test_is_not_empty_with_product(self):
        """Test is_empty returns False when product is set."""
        filter_params = ContractsFilter(product="Gas")
        assert filter_params.is_empty() is False

    def test_is_not_empty_with_delivery_market(self):
        """Test is_empty returns False when delivery_market is set."""
        filter_params = ContractsFilter(market="EUROPE")
        assert filter_params.is_empty() is False
