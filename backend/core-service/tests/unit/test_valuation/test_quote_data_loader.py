"""Unit tests for quote_data_loader module.

Tests parquet loading with date-range filtering and averaging (via DuckDB),
CSV fallback, and error handling.
"""

import datetime as dt
import io
from unittest.mock import Mock, patch

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from fastapi import HTTPException

from domains.risk.services.quote_data_loader import (
    _load_quote_from_csv,
    _load_quote_from_parquet,
    _resolve_quote_path,
    _to_ordinal,
    load_quote_as_dataframe,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _create_parquet_bytes(df: pd.DataFrame) -> bytes:
    """Serialize a DataFrame to parquet bytes."""
    buf = io.BytesIO()
    table = pa.Table.from_pandas(df, preserve_index=False)
    pq.write_table(table, buf)
    buf.seek(0)
    return buf.getvalue()


def _create_mock_storage_path(full_path: str, exists: bool = True):
    """Create a mock StoragePath with the given full_path and exists status."""
    mock_path = Mock()
    mock_path.full_path = full_path
    mock_path.exists = Mock(return_value=exists)
    return mock_path


def _write_parquet_file(path, df: pd.DataFrame):
    """Write a DataFrame to a parquet file at the given path."""
    table = pa.Table.from_pandas(df, preserve_index=False)
    pq.write_table(table, str(path))


# ---------------------------------------------------------------------------
# _to_ordinal tests
# ---------------------------------------------------------------------------


class TestToOrdinal:
    """Tests for the _to_ordinal helper function."""

    def test_int_value(self):
        assert _to_ordinal(738000) == 738000

    def test_numpy_integer(self):
        assert _to_ordinal(np.int64(738000)) == 738000

    def test_date_value(self):
        date_val = dt.date(2026, 1, 1)
        assert _to_ordinal(date_val) == date_val.toordinal()

    def test_datetime_value(self):
        dt_val = dt.datetime(2026, 1, 1, 12, 0)
        assert _to_ordinal(dt_val) == dt_val.date().toordinal()

    def test_string_value(self):
        assert _to_ordinal("2026-01-01") == dt.date(2026, 1, 1).toordinal()

    def test_unsupported_type_raises(self):
        with pytest.raises(ValueError, match="Unsupported date type"):
            _to_ordinal([2026, 1, 1])


# ---------------------------------------------------------------------------
# _resolve_quote_path tests
# ---------------------------------------------------------------------------


class TestResolveQuotePath:
    """Tests for the _resolve_quote_path helper function."""

    def test_parquet_exists_returns_path(self):
        mock_path = _create_mock_storage_path("/data/quote/BRENT_DATED.parquet", exists=True)
        with patch(
            "domains.risk.services.quote_data_loader.FileStoreRegistry"
        ) as mock_registry_cls:
            mock_registry = Mock()
            mock_registry.simulation_source_path = Mock(
                return_value=Mock(**{"__truediv__": lambda s, x: mock_path})
            )
            mock_registry_cls.return_value = mock_registry
            result = _resolve_quote_path("BRENT_DATED", dt.date(2026, 1, 1), "parquet")
            assert result == mock_path

    def test_parquet_not_exists_returns_none(self):
        mock_path = _create_mock_storage_path("/data/quote/BRENT_DATED.parquet", exists=False)
        with patch(
            "domains.risk.services.quote_data_loader.FileStoreRegistry"
        ) as mock_registry_cls:
            mock_registry = Mock()
            mock_registry.simulation_source_path = Mock(
                return_value=Mock(**{"__truediv__": lambda s, x: mock_path})
            )
            mock_registry_cls.return_value = mock_registry
            result = _resolve_quote_path("BRENT_DATED", dt.date(2026, 1, 1), "parquet")
            assert result is None

    def test_csv_exists_returns_path(self):
        mock_path = _create_mock_storage_path("/data/quote/BRENT_DATED.csv", exists=True)
        with patch(
            "domains.risk.services.quote_data_loader.FileStoreRegistry"
        ) as mock_registry_cls:
            mock_registry = Mock()
            mock_registry.simulation_source_path = Mock(
                return_value=Mock(**{"__truediv__": lambda s, x: mock_path})
            )
            mock_registry_cls.return_value = mock_registry
            result = _resolve_quote_path("BRENT_DATED", dt.date(2026, 1, 1), "csv")
            assert result == mock_path


# ---------------------------------------------------------------------------
# _load_quote_from_parquet tests (DuckDB-based)
# ---------------------------------------------------------------------------


class TestLoadQuoteFromParquet:
    """Tests for DuckDB-based parquet loading with date-range filtering and averaging."""

    def test_basic_loading_and_averaging(self, tmp_path):
        """Test basic parquet loading: dates in rows, sample_index in columns."""
        # Create test parquet data: 3 dates, 3 samples
        test_df = pd.DataFrame(
            {
                "date": [
                    dt.date(2026, 1, 1),
                    dt.date(2026, 2, 1),
                    dt.date(2026, 3, 1),
                ],
                "sample_0": [100.0, 110.0, 120.0],
                "sample_1": [200.0, 210.0, 220.0],
                "sample_2": [300.0, 310.0, 320.0],
            }
        )

        parquet_file = tmp_path / "BRENT_DATED.parquet"
        _write_parquet_file(parquet_file, test_df)

        mock_path = _create_mock_storage_path(str(parquet_file))

        period_from = dt.date(2026, 1, 1)
        period_to = dt.date(2026, 2, 28)

        # Mock the FileStoreRegistry and DuckDbStorageAdapter
        with patch(
            "domains.risk.services.quote_data_loader.FileStoreRegistry"
        ) as mock_registry_cls:
            mock_registry = Mock()
            mock_registry.simulation_source = Mock()
            mock_registry_cls.return_value = mock_registry

            with patch(
                "domains.risk.services.quote_data_loader.DuckDbStorageAdapter"
            ) as mock_adapter_cls:
                mock_adapter = Mock()
                mock_adapter.to_duckdb_path = Mock(return_value=str(parquet_file))
                mock_adapter.configure = Mock()
                mock_adapter_cls.return_value = mock_adapter

                result = _load_quote_from_parquet(mock_path, period_from, period_to, "BRENT_DATED")

        # Expected: average of Jan and Feb rows
        # sample_0: (100 + 110) / 2 = 105.0
        # sample_1: (200 + 210) / 2 = 205.0
        # sample_2: (300 + 310) / 2 = 305.0
        assert len(result) == 3
        assert list(result.columns) == ["sample_index", "BRENT_DATED"]
        assert result.iloc[0]["sample_index"] == 0
        assert result.iloc[0]["BRENT_DATED"] == pytest.approx(105.0)
        assert result.iloc[1]["sample_index"] == 1
        assert result.iloc[1]["BRENT_DATED"] == pytest.approx(205.0)
        assert result.iloc[2]["sample_index"] == 2
        assert result.iloc[2]["BRENT_DATED"] == pytest.approx(305.0)

    def test_single_date_range(self, tmp_path):
        """Test with a date range that matches only one row."""
        test_df = pd.DataFrame(
            {
                "date": [
                    dt.date(2026, 1, 1),
                    dt.date(2026, 2, 1),
                    dt.date(2026, 3, 1),
                ],
                "sample_0": [100.0, 110.0, 120.0],
                "sample_1": [200.0, 210.0, 220.0],
            }
        )

        parquet_file = tmp_path / "BRENT_DATED.parquet"
        _write_parquet_file(parquet_file, test_df)

        mock_path = _create_mock_storage_path(str(parquet_file))

        # Only February matches
        period_from = dt.date(2026, 2, 1)
        period_to = dt.date(2026, 2, 28)

        with patch(
            "domains.risk.services.quote_data_loader.FileStoreRegistry"
        ) as mock_registry_cls:
            mock_registry = Mock()
            mock_registry.simulation_source = Mock()
            mock_registry_cls.return_value = mock_registry

            with patch(
                "domains.risk.services.quote_data_loader.DuckDbStorageAdapter"
            ) as mock_adapter_cls:
                mock_adapter = Mock()
                mock_adapter.to_duckdb_path = Mock(return_value=str(parquet_file))
                mock_adapter.configure = Mock()
                mock_adapter_cls.return_value = mock_adapter

                result = _load_quote_from_parquet(mock_path, period_from, period_to, "BRENT_DATED")

        assert len(result) == 2
        assert result.iloc[0]["BRENT_DATED"] == 110.0
        assert result.iloc[1]["BRENT_DATED"] == 210.0

    def test_no_matching_dates_raises(self, tmp_path):
        """Test that an empty date range raises HTTPException."""
        test_df = pd.DataFrame(
            {
                "date": [
                    dt.date(2026, 1, 1),
                    dt.date(2026, 2, 1),
                ],
                "sample_0": [100.0, 110.0],
            }
        )

        parquet_file = tmp_path / "BRENT_DATED.parquet"
        _write_parquet_file(parquet_file, test_df)

        mock_path = _create_mock_storage_path(str(parquet_file))

        # March doesn't match any rows
        period_from = dt.date(2026, 3, 1)
        period_to = dt.date(2026, 3, 31)

        with patch(
            "domains.risk.services.quote_data_loader.FileStoreRegistry"
        ) as mock_registry_cls:
            mock_registry = Mock()
            mock_registry.simulation_source = Mock()
            mock_registry_cls.return_value = mock_registry

            with patch(
                "domains.risk.services.quote_data_loader.DuckDbStorageAdapter"
            ) as mock_adapter_cls:
                mock_adapter = Mock()
                mock_adapter.to_duckdb_path = Mock(return_value=str(parquet_file))
                mock_adapter.configure = Mock()
                mock_adapter_cls.return_value = mock_adapter

                with pytest.raises(HTTPException, match="No quote data found for date range"):
                    _load_quote_from_parquet(mock_path, period_from, period_to, "BRENT_DATED")

    def test_empty_parquet_raises(self, tmp_path):
        """Test that an empty parquet file raises HTTPException.

        Note: DuckDB can read schema from empty parquet files, so the error
        message is "No quote data found" rather than "empty or has invalid schema".
        """
        empty_df = pd.DataFrame({"date": [], "sample_0": []})

        parquet_file = tmp_path / "BRENT_DATED.parquet"
        _write_parquet_file(parquet_file, empty_df)

        mock_path = _create_mock_storage_path(str(parquet_file))

        with patch(
            "domains.risk.services.quote_data_loader.FileStoreRegistry"
        ) as mock_registry_cls:
            mock_registry = Mock()
            mock_registry.simulation_source = Mock()
            mock_registry_cls.return_value = mock_registry

            with patch(
                "domains.risk.services.quote_data_loader.DuckDbStorageAdapter"
            ) as mock_adapter_cls:
                mock_adapter = Mock()
                mock_adapter.to_duckdb_path = Mock(return_value=str(parquet_file))
                mock_adapter.configure = Mock()
                mock_adapter_cls.return_value = mock_adapter

                # Empty parquet with valid schema returns "No quote data found"
                with pytest.raises(HTTPException, match="No quote data found"):
                    _load_quote_from_parquet(
                        mock_path,
                        dt.date(2026, 1, 1),
                        dt.date(2026, 1, 31),
                        "BRENT_DATED",
                    )

    def test_numeric_column_names(self, tmp_path):
        """Test parquet with numeric column names instead of sample_N format."""
        test_df = pd.DataFrame(
            {
                "date": [
                    dt.date(2026, 1, 1),
                    dt.date(2026, 2, 1),
                ],
                "0": [100.0, 110.0],
                "1": [200.0, 210.0],
            }
        )

        parquet_file = tmp_path / "BRENT_DATED.parquet"
        _write_parquet_file(parquet_file, test_df)

        mock_path = _create_mock_storage_path(str(parquet_file))

        with patch(
            "domains.risk.services.quote_data_loader.FileStoreRegistry"
        ) as mock_registry_cls:
            mock_registry = Mock()
            mock_registry.simulation_source = Mock()
            mock_registry_cls.return_value = mock_registry

            with patch(
                "domains.risk.services.quote_data_loader.DuckDbStorageAdapter"
            ) as mock_adapter_cls:
                mock_adapter = Mock()
                mock_adapter.to_duckdb_path = Mock(return_value=str(parquet_file))
                mock_adapter.configure = Mock()
                mock_adapter_cls.return_value = mock_adapter

                result = _load_quote_from_parquet(
                    mock_path, dt.date(2026, 1, 1), dt.date(2026, 2, 28), "BRENT_DATED"
                )

        assert len(result) == 2
        assert result.iloc[0]["sample_index"] == 0
        assert result.iloc[1]["sample_index"] == 1

    def test_sorted_by_sample_index(self, tmp_path):
        """Test that result is sorted by sample_index (ordinal position, not column name).

        sample_index is the ordinal position of the column in the parquet file (0, 1, 2, ...),
        NOT the number extracted from the column name. This matches the original pandas behavior.
        """
        test_df = pd.DataFrame(
            {
                "date": [
                    dt.date(2026, 1, 1),
                ],
                "sample_5": [500.0],
                "sample_0": [100.0],
                "sample_3": [300.0],
            }
        )

        parquet_file = tmp_path / "BRENT_DATED.parquet"
        _write_parquet_file(parquet_file, test_df)

        mock_path = _create_mock_storage_path(str(parquet_file))

        with patch(
            "domains.risk.services.quote_data_loader.FileStoreRegistry"
        ) as mock_registry_cls:
            mock_registry = Mock()
            mock_registry.simulation_source = Mock()
            mock_registry_cls.return_value = mock_registry

            with patch(
                "domains.risk.services.quote_data_loader.DuckDbStorageAdapter"
            ) as mock_adapter_cls:
                mock_adapter = Mock()
                mock_adapter.to_duckdb_path = Mock(return_value=str(parquet_file))
                mock_adapter.configure = Mock()
                mock_adapter_cls.return_value = mock_adapter

                result = _load_quote_from_parquet(
                    mock_path, dt.date(2026, 1, 1), dt.date(2026, 1, 31), "BRENT_DATED"
                )

        # sample_index = ordinal position (0, 1, 2), not column name numbers (5, 0, 3)
        # Values correspond to: sample_5=500, sample_0=100, sample_3=300
        assert list(result["sample_index"]) == [0, 1, 2]
        assert list(result["BRENT_DATED"]) == [500.0, 100.0, 300.0]


# ---------------------------------------------------------------------------
# _load_quote_from_csv tests
# ---------------------------------------------------------------------------


class TestLoadQuoteFromCsv:
    """Tests for CSV fallback loading."""

    def test_basic_csv_loading(self, tmp_path):
        """Test basic CSV loading with sample_index and value column."""
        csv_file = tmp_path / "BRENT_DATED.csv"
        csv_file.write_text("sample_index,BRENT_DATED\n0,100.0\n1,110.0\n2,120.0\n")

        mock_path = _create_mock_storage_path(str(csv_file), exists=True)
        result = _load_quote_from_csv(mock_path, "BRENT_DATED")

        assert len(result) == 3
        assert list(result.columns) == ["sample_index", "BRENT_DATED"]
        assert result.iloc[0]["sample_index"] == 0
        assert result.iloc[0]["BRENT_DATED"] == 100.0

    def test_csv_without_sample_index_column(self, tmp_path):
        """Test CSV loading when sample_index column is missing (auto-generated)."""
        csv_file = tmp_path / "BRENT_DATED.csv"
        csv_file.write_text("BRENT_DATED\n100.0\n110.0\n120.0\n")

        mock_path = _create_mock_storage_path(str(csv_file), exists=True)
        result = _load_quote_from_csv(mock_path, "BRENT_DATED")

        assert len(result) == 3
        assert list(result.columns) == ["sample_index", "BRENT_DATED"]
        assert result.iloc[0]["sample_index"] == 0
        assert result.iloc[1]["sample_index"] == 1

    def test_csv_multiple_value_columns_raises(self, tmp_path):
        """Test CSV with multiple value columns raises HTTPException."""
        csv_file = tmp_path / "BRENT_DATED.csv"
        csv_file.write_text("sample_index,BRENT_DATED,EXTRA\n0,100.0,999\n1,110.0,888\n")

        mock_path = _create_mock_storage_path(str(csv_file), exists=True)

        with pytest.raises(HTTPException, match="Cannot resolve quote column"):
            _load_quote_from_csv(mock_path, "BRENT_DATED")


# ---------------------------------------------------------------------------
# load_quote_as_dataframe integration tests
# ---------------------------------------------------------------------------


class TestLoadQuoteAsDataframe:
    """Tests for the main entry point function."""

    def test_parquet_preferred_over_csv(self, tmp_path):
        """Test that parquet is tried first and preferred over CSV."""
        parquet_df = pd.DataFrame(
            {
                "date": [dt.date(2026, 1, 1)],
                "sample_0": [100.0],
            }
        )

        parquet_file = tmp_path / "BRENT_DATED.parquet"
        _write_parquet_file(parquet_file, parquet_df)

        mock_parquet_path = _create_mock_storage_path(str(parquet_file), exists=True)
        mock_csv_path = _create_mock_storage_path(str(tmp_path / "BRENT_DATED.csv"), exists=True)

        call_order = []

        def mock_resolve(name, obs_date, fmt):
            call_order.append(fmt)
            if fmt == "parquet":
                return mock_parquet_path
            return mock_csv_path

        with patch(
            "domains.risk.services.quote_data_loader._resolve_quote_path",
            side_effect=mock_resolve,
        ):
            with patch(
                "domains.risk.services.quote_data_loader.FileStoreRegistry"
            ) as mock_registry_cls:
                mock_registry = Mock()
                mock_registry.simulation_source = Mock()
                mock_registry_cls.return_value = mock_registry

                with patch(
                    "domains.risk.services.quote_data_loader.DuckDbStorageAdapter"
                ) as mock_adapter_cls:
                    mock_adapter = Mock()
                    mock_adapter.to_duckdb_path = Mock(return_value=str(parquet_file))
                    mock_adapter.configure = Mock()
                    mock_adapter_cls.return_value = mock_adapter

                    result = load_quote_as_dataframe(
                        "BRENT_DATED",
                        dt.date(2026, 1, 1),
                        dt.date(2026, 1, 1),
                        dt.date(2026, 1, 31),
                    )

        # Parquet should be tried first
        assert call_order[0] == "parquet"
        assert len(result) == 1
        assert result.iloc[0]["BRENT_DATED"] == 100.0

    def test_csv_fallback_when_parquet_not_found(self, tmp_path):
        """Test CSV fallback when parquet file does not exist."""
        csv_df = pd.DataFrame(
            {
                "sample_index": [0, 1],
                "VALUE": [100.0, 110.0],
            }
        )
        mock_csv_path = _create_mock_storage_path(str(tmp_path / "BRENT_DATED.csv"), exists=True)

        def mock_resolve(name, obs_date, fmt):
            if fmt == "parquet":
                return None  # Parquet not found
            return mock_csv_path

        with patch(
            "domains.risk.services.quote_data_loader._resolve_quote_path",
            side_effect=mock_resolve,
        ):
            with patch("pandas.read_csv", return_value=csv_df):
                result = load_quote_as_dataframe(
                    "BRENT_DATED",
                    dt.date(2026, 1, 1),
                    dt.date(2026, 1, 1),
                    dt.date(2026, 1, 31),
                )

        assert len(result) == 2
        assert result.iloc[0]["BRENT_DATED"] == 100.0

    def test_neither_file_exists_raises_404(self):
        """Test that HTTPException 404 is raised when neither file exists."""
        with patch(
            "domains.risk.services.quote_data_loader._resolve_quote_path",
            return_value=None,
        ):
            with pytest.raises(HTTPException, match="Quote file not found"):
                load_quote_as_dataframe(
                    "BRENT_DATED",
                    dt.date(2026, 1, 1),
                    dt.date(2026, 1, 1),
                    dt.date(2026, 1, 31),
                )
