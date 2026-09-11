"""Unit tests for unified Hive storage structure.

Tests the unified Hive-partitioned Parquet structure with:
- run_mode / valuation_type / observation_date partitioning (run_mode first)
- run_mode: deterministic or simulation
- valuation_type: eod, eom, eoy, forecast, UUID
- No simulation_type partition (removed as it carries no useful information)
"""

import datetime
from unittest.mock import MagicMock, Mock

import pandas as pd
import pytest

from domains.reporting.services.hive_parquet_writer import (
    HiveParquetWriter,
    _build_partition_path,
)


class TestBuildPartitionPath:
    """Tests for _build_partition_path function."""

    def test_build_partition_path_with_eod_valuation_type(self):
        """Test that partition path starts with observation_date, run_mode, then valuation_type."""
        path = _build_partition_path(
            observation_date=datetime.date(2026, 6, 21),
            valuation_type="eod",
            run_mode="simulation",
            valuation_period="2026-06-01",
            gl_account="OP_REV_SALES",
            market="TTF",
            product="Gas",
            hive_base_path="executions/data",
            scenario="default",
        )

        assert path == (
            "executions/data/fact_simulation/"
            "observation_date=20260621/"
            "run_mode=simulation/"
            "valuation_type=eod/"
            "valuation_year=2026/"
            "valuation_month=06/"
            "gl_account=OP_REV_SALES/"
            "market=TTF/"
            "product=Gas/"
            "scenario=default"
        )

    def test_build_partition_path_with_custom_valuation_type(self):
        """Test that partition path includes custom valuation_type (UUID)."""
        valuation_type = "550e8400-e29b-41d4-a716-446655440000"
        path = _build_partition_path(
            observation_date=datetime.date(2026, 6, 21),
            valuation_type=valuation_type,
            run_mode="simulation",
            valuation_period="2026-06-01",
            gl_account="OP_REV_SALES",
            market="TTF",
            product="Gas",
            hive_base_path="executions/data",
            scenario="default",
        )

        assert f"valuation_type={valuation_type}" in path
        assert "observation_date=20260621" in path

    def test_build_partition_path_uses_canonical_partition_order(self):
        """Test observation_date, run_mode, and valuation_type ordering."""
        path = _build_partition_path(
            observation_date=datetime.date(2026, 6, 21),
            valuation_type="eod",
            run_mode="simulation",
            valuation_period="2026-06-01",
            gl_account="OP_REV_SALES",
            market="TTF",
            product="Gas",
            hive_base_path="executions/data",
            scenario="default",
        )

        rm_pos = path.index("run_mode=")
        vt_pos = path.index("valuation_type=")
        obs_pos = path.index("observation_date=")
        assert obs_pos < rm_pos < vt_pos

    def test_build_partition_path_no_simulation_type(self):
        """Test that simulation_type is NOT present in the partition path."""
        path = _build_partition_path(
            observation_date=datetime.date(2026, 6, 21),
            valuation_type="eod",
            run_mode="simulation",
            valuation_period="2026-06-01",
            gl_account="OP_REV_SALES",
            market="TTF",
            product="Gas",
            hive_base_path="executions/data",
            scenario="default",
        )

        assert "simulation_type" not in path

    def test_build_partition_path_with_none_values(self):
        """Test that partition path handles None values correctly."""
        path = _build_partition_path(
            observation_date=datetime.date(2026, 6, 21),
            valuation_type="eod",
            run_mode="simulation",
            valuation_period="2026-06-01",
            gl_account=None,
            market=None,
            product=None,
            hive_base_path="executions/data",
            scenario=None,
        )

        assert "gl_account=__HIVE_DEFAULT_PARTITION__" in path
        assert "market=__HIVE_DEFAULT_PARTITION__" in path
        assert "product=__HIVE_DEFAULT_PARTITION__" in path
        assert "scenario=__HIVE_DEFAULT_PARTITION__" in path

    def test_build_partition_path_with_datetime_valuation_period(self):
        """Test that partition path handles datetime valuation_period correctly."""
        path = _build_partition_path(
            observation_date=datetime.date(2026, 6, 21),
            valuation_type="eod",
            run_mode="simulation",
            valuation_period=datetime.date(2026, 7, 15),
            gl_account="OP_REV_SALES",
            market="TTF",
            product="Gas",
            hive_base_path="executions/data",
            scenario="default",
        )

        assert "valuation_year=2026" in path
        assert "valuation_month=07" in path


class TestHiveParquetWriter:
    """Tests for HiveParquetWriter class."""

    @pytest.fixture
    def mock_storage_fs(self):
        """Create a mock StorageFS for testing."""
        mock_fs = MagicMock()
        mock_path = MagicMock()
        mock_fs.__truediv__ = Mock(return_value=mock_path)
        mock_path.open = MagicMock()
        return mock_fs

    def test_writer_initialization_with_valuation_type(self, mock_storage_fs):
        """Test that HiveParquetWriter initializes with valuation_type and run_mode."""
        writer = HiveParquetWriter(
            storage_fs=mock_storage_fs,
            observation_date=datetime.date(2026, 6, 21),
            valuation_type="eod",
            run_mode="simulation",
            hive_base_path="executions/data",
        )

        assert writer._observation_date == datetime.date(2026, 6, 21)
        assert writer._valuation_type == "eod"
        assert writer._run_mode == "simulation"
        assert writer._hive_base_path == "executions/data"

    def test_write_with_different_valuation_types(self, mock_storage_fs):
        """Test writing with different valuation types."""
        df = pd.DataFrame(
            {
                "valuation_period": ["2026-06-01"],
                "gl_account": ["OP_REV_SALES"],
                "market": ["TTF"],
                "product": ["Gas"],
                "scenario": ["default"],
                "sample_index": [0],
                "supply_path": ["stream_a"],
                "legal_entity": ["entity_a"],
                "payment_period": ["2026-07-01"],
                "value_usd": [100.0],
                "value_rub": [9000.0],
                "volume": [10.0],
            }
        )

        # Test eod
        writer_eod = HiveParquetWriter(
            storage_fs=mock_storage_fs,
            observation_date=datetime.date(2026, 6, 21),
            valuation_type="eod",
            run_mode="simulation",
        )
        writer_eod.write(df)

        # Test eom
        writer_eom = HiveParquetWriter(
            storage_fs=mock_storage_fs,
            observation_date=datetime.date(2026, 6, 21),
            valuation_type="eom",
            run_mode="simulation",
        )
        writer_eom.write(df)

        # Test forecast
        writer_forecast = HiveParquetWriter(
            storage_fs=mock_storage_fs,
            observation_date=datetime.date(2026, 6, 21),
            valuation_type="forecast",
            run_mode="simulation",
        )
        writer_forecast.write(df)

    def test_write_with_custom_valuation_type(self, mock_storage_fs):
        """Test writing with custom valuation_type (UUID)."""
        df = pd.DataFrame(
            {
                "valuation_period": ["2026-06-01"],
                "gl_account": ["OP_REV_SALES"],
                "market": ["TTF"],
                "product": ["Gas"],
                "scenario": ["default"],
                "sample_index": [0],
                "supply_path": ["stream_a"],
                "legal_entity": ["entity_a"],
                "payment_period": ["2026-07-01"],
                "value_usd": [100.0],
                "value_rub": [9000.0],
                "volume": [10.0],
            }
        )

        valuation_type = "550e8400-e29b-41d4-a716-446655440000"
        writer = HiveParquetWriter(
            storage_fs=mock_storage_fs,
            observation_date=datetime.date(2026, 6, 21),
            valuation_type=valuation_type,
            run_mode="simulation",
        )
        writer.write(df)

    def test_write_empty_dataframe(self, mock_storage_fs):
        """Test that writing empty DataFrame does not raise error."""
        df = pd.DataFrame()

        writer = HiveParquetWriter(
            storage_fs=mock_storage_fs,
            observation_date=datetime.date(2026, 6, 21),
            valuation_type="eod",
            run_mode="simulation",
        )

        # Should not raise error
        writer.write(df)
