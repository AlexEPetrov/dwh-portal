"""Unit tests for HiveParquetWriter."""

import datetime
import io
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pandas as pd
import pyarrow.parquet as pq
import pytest

from domains.reporting.services.hive_parquet_writer import (
    HiveParquetWriter,
    _build_partition_path,
    _safe_partition_value,
)


class TestSafePartitionValue:
    """Tests for _safe_partition_value helper."""

    def test_normal_string(self):
        assert _safe_partition_value("OP_REV_SALES") == "OP_REV_SALES"

    def test_none_value(self):
        assert _safe_partition_value(None) == "__HIVE_DEFAULT_PARTITION__"

    def test_empty_string(self):
        assert _safe_partition_value("") == "__HIVE_DEFAULT_PARTITION__"

    def test_whitespace_string(self):
        assert _safe_partition_value("   ") == "__HIVE_DEFAULT_PARTITION__"

    def test_nan_float(self):
        import numpy as np

        assert _safe_partition_value(np.nan) == "__HIVE_DEFAULT_PARTITION__"  # type: ignore[arg-type]

    def test_path_separator_replacement(self):
        assert _safe_partition_value("market/region") == "market_region"

    def test_backslash_replacement(self):
        assert _safe_partition_value("market\\region") == "market_region"


class TestBuildPartitionPath:
    """Tests for _build_partition_path helper."""

    def test_basic_path_construction(self):
        obs_date = datetime.date(2026, 5, 7)
        path = _build_partition_path(
            observation_date=obs_date,
            valuation_type="eod",
            run_mode="simulation",
            valuation_period="2026-05-01",
            gl_account="OP_REV_SALES",
            market="Europe",
            product="Oil",
            hive_base_path="hive_results",
            scenario="base",
        )
        expected = (
            "hive_results/fact_simulation/observation_date=20260507/run_mode=simulation/valuation_type=eod/valuation_year=2026/"
            "valuation_month=05/gl_account=OP_REV_SALES/market=Europe/product=Oil/scenario=base"
        )
        assert path == expected

    def test_delegates_to_shared_builder(self, monkeypatch):
        delegated = MagicMock(return_value="canonical/path")
        monkeypatch.setattr(
            "domains.reporting.services.hive_parquet_writer.build_fact_partition_path",
            delegated,
        )

        path = _build_partition_path(
            observation_date=datetime.date(2026, 5, 7),
            valuation_type="eod",
            run_mode="simulation",
            valuation_period="2026-05-01",
            gl_account="OP_REV_SALES",
            market="Europe",
            product="Oil",
            hive_base_path="executions/data",
            scenario="base",
        )

        assert path == "canonical/path"
        delegated.assert_called_once_with(
            "executions/data",
            observation_date=datetime.date(2026, 5, 7),
            run_mode="simulation",
            valuation_type="eod",
            valuation_period="2026-05-01",
            gl_account="OP_REV_SALES",
            market="Europe",
            product="Oil",
            scenario="base",
        )

    def test_null_gl_account(self):
        obs_date = datetime.date(2026, 5, 7)
        path = _build_partition_path(
            observation_date=obs_date,
            valuation_type="eod",
            run_mode="simulation",
            valuation_period="2026-05-01",
            gl_account=None,
            market="Europe",
            product="Oil",
            hive_base_path="hive_results",
            scenario="base",
        )
        assert "gl_account=__HIVE_DEFAULT_PARTITION__" in path

    def test_null_market(self):
        obs_date = datetime.date(2026, 5, 7)
        path = _build_partition_path(
            observation_date=obs_date,
            valuation_type="eod",
            run_mode="simulation",
            valuation_period="2026-05-01",
            gl_account="OP_REV_SALES",
            market=None,
            product="Oil",
            hive_base_path="hive_results",
            scenario="base",
        )
        assert "market=__HIVE_DEFAULT_PARTITION__" in path

    def test_null_product(self):
        obs_date = datetime.date(2026, 5, 7)
        path = _build_partition_path(
            observation_date=obs_date,
            valuation_type="eod",
            run_mode="simulation",
            valuation_period="2026-05-01",
            gl_account="OP_REV_SALES",
            market="Europe",
            product=None,
            hive_base_path="hive_results",
            scenario="base",
        )
        assert "product=__HIVE_DEFAULT_PARTITION__" in path

    def test_null_scenario(self):
        obs_date = datetime.date(2026, 5, 7)
        path = _build_partition_path(
            observation_date=obs_date,
            valuation_type="eod",
            run_mode="simulation",
            valuation_period="2026-05-01",
            gl_account="OP_REV_SALES",
            market="Europe",
            product="Oil",
            hive_base_path="hive_results",
            scenario=None,
        )
        assert "scenario=__HIVE_DEFAULT_PARTITION__" in path

    def test_date_object_valuation_period(self):
        obs_date = datetime.date(2026, 5, 7)
        val_date = datetime.date(2026, 3, 15)
        path = _build_partition_path(
            observation_date=obs_date,
            valuation_type="eod",
            run_mode="simulation",
            valuation_period=val_date,
            gl_account="OP_TAX_DUTY",
            market="Asia",
            product="Gas",
            hive_base_path="parquet_output",
            scenario="stress",
        )
        assert "valuation_year=2026" in path
        assert "valuation_month=03" in path
        assert "scenario=stress" in path

    def test_empty_valuation_period(self):
        obs_date = datetime.date(2026, 5, 7)
        with pytest.raises(ValueError, match="valuation_period"):
            _build_partition_path(
                observation_date=obs_date,
                valuation_type="eod",
                run_mode="simulation",
                valuation_period="",
                gl_account="OP_REV_SALES",
                market="Europe",
                product="Oil",
                hive_base_path="hive_results",
                scenario="base",
            )

    def test_custom_base_path(self):
        obs_date = datetime.date(2026, 5, 7)
        path = _build_partition_path(
            observation_date=obs_date,
            valuation_type="eod",
            run_mode="simulation",
            valuation_period="2026-05-01",
            gl_account="OP_REV_SALES",
            market="Europe",
            product="Oil",
            hive_base_path="custom/hive/path",
            scenario="base",
        )
        assert path.startswith("custom/hive/path/fact_simulation/observation_date=")


class TestHiveParquetWriter:
    """Tests for HiveParquetWriter class."""

    def _create_mock_storage_fs(self):
        """Create a mock StorageFS that captures written files."""
        written_files = {}

        class MockStoragePath:
            """Mimics StoragePath behavior."""

            def __init__(self, path_str):
                self._path = path_str

            def open(self, mode="rb"):
                buf = io.BytesIO()
                written_files[self._path] = buf
                # Return a context manager
                cm = MagicMock()
                cm.__enter__ = MagicMock(return_value=buf)
                cm.__exit__ = MagicMock(return_value=False)
                return cm

        class MockStorageFS:
            """Mimics StorageFS behavior."""

            def __truediv__(self, path_str):
                return MockStoragePath(path_str)

        return MockStorageFS(), written_files

    def test_write_empty_dataframe(self):
        """Empty DataFrame should be skipped without writing."""
        mock_storage, written_files = self._create_mock_storage_fs()
        obs_date = datetime.date(2026, 5, 7)
        writer = HiveParquetWriter(mock_storage, obs_date, "eod", "simulation", "hive_results")

        df = pd.DataFrame()
        writer.write(df)

        assert len(written_files) == 0

    def test_write_single_partition(self):
        """DataFrame with one group should produce one parquet file."""
        mock_storage, written_files = self._create_mock_storage_fs()
        obs_date = datetime.date(2026, 5, 7)
        writer = HiveParquetWriter(mock_storage, obs_date, "eod", "simulation", "hive_results")

        df = pd.DataFrame(
            {
                "sample_index": [0, 0],
                "scenario": ["base", "base"],
                "supply_path": ["sp1", "sp1"],
                "legal_entity": ["entity1", "entity1"],
                "payment_period": ["2026-05-01", "2026-05-01"],
                "value_usd": [100.0, 200.0],
                "value_rub": [9000.0, 18000.0],
                "volume": [10.0, 20.0],
                "valuation_period": ["2026-05-01", "2026-05-01"],
                "gl_account": ["OP_REV_SALES", "OP_REV_SALES"],
                "market": ["Europe", "Europe"],
                "product": ["Oil", "Oil"],
            }
        )

        writer.write(df)

        assert len(written_files) == 1
        # Check that the path contains expected partition keys
        written_path = list(written_files.keys())[0]
        assert "observation_date=20260507" in written_path
        assert "scenario=base" in written_path
        assert "valuation_year=2026" in written_path
        assert "valuation_month=05" in written_path
        assert "gl_account=OP_REV_SALES" in written_path
        assert "market=Europe" in written_path
        assert "product=Oil" in written_path
        assert written_path.endswith("/data.parquet")

    def test_write_multiple_partitions(self):
        """DataFrame with multiple groups should produce multiple parquet files."""
        mock_storage, written_files = self._create_mock_storage_fs()
        obs_date = datetime.date(2026, 5, 7)
        writer = HiveParquetWriter(mock_storage, obs_date, "eod", "simulation", "hive_results")

        df = pd.DataFrame(
            {
                "sample_index": [0, 0, 0, 0],
                "scenario": ["base", "base", "base", "base"],
                "supply_path": ["sp1", "sp1", "sp2", "sp2"],
                "legal_entity": ["entity1", "entity1", "entity1", "entity1"],
                "payment_period": ["2026-05-01", "2026-05-01", "2026-06-01", "2026-06-01"],
                "value_usd": [100.0, 200.0, 300.0, 400.0],
                "value_rub": [9000.0, 18000.0, 27000.0, 36000.0],
                "volume": [10.0, 20.0, 30.0, 40.0],
                "valuation_period": ["2026-05-01", "2026-05-01", "2026-06-01", "2026-06-01"],
                "gl_account": ["OP_REV_SALES", "OP_REV_SALES", "OP_TAX_DUTY", "OP_TAX_DUTY"],
                "market": ["Europe", "Europe", "Asia", "Asia"],
                "product": ["Oil", "Oil", "Gas", "Gas"],
            }
        )

        writer.write(df)

        assert len(written_files) == 2

    def test_write_with_null_partition_values(self):
        """NULL values in partition columns should use placeholder."""
        import numpy as np

        mock_storage, written_files = self._create_mock_storage_fs()
        obs_date = datetime.date(2026, 5, 7)
        writer = HiveParquetWriter(mock_storage, obs_date, "eod", "simulation", "hive_results")

        # Use pd.NA-like values that pandas groupby produces
        df = pd.DataFrame(
            {
                "sample_index": [0],
                "scenario": ["base"],
                "supply_path": ["sp1"],
                "legal_entity": ["entity1"],
                "payment_period": ["2026-05-01"],
                "value_usd": [100.0],
                "value_rub": [9000.0],
                "volume": [10.0],
                "valuation_period": ["2026-05-01"],
                "gl_account": [np.nan],
                "market": [np.nan],
                "product": [np.nan],
            }
        )

        writer.write(df)

        assert len(written_files) == 1
        written_path = list(written_files.keys())[0]
        assert "gl_account=__HIVE_DEFAULT_PARTITION__" in written_path
        assert "market=__HIVE_DEFAULT_PARTITION__" in written_path
        assert "product=__HIVE_DEFAULT_PARTITION__" in written_path

    def test_parquet_file_is_readable(self):
        """Written parquet file should be readable back via pyarrow."""
        import pyarrow as pa

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            parquet_file = tmp_path / "test_data.parquet"

            df = pd.DataFrame(
                {
                    "sample_index": [0, 1],
                    "value_usd": [100.0, 200.0],
                    "value_rub": [9000.0, 18000.0],
                }
            )

            table = pa.Table.from_pandas(df, preserve_index=False)
            pq.write_table(table, parquet_file, compression="zstd")

            # Read back
            read_table = pq.read_table(parquet_file)
            read_df = read_table.to_pandas()

            assert len(read_df) == 2
            assert "sample_index" in read_df.columns
            assert "value_usd" in read_df.columns
