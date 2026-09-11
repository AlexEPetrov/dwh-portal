"""Unit tests for Excel source reader module."""

from __future__ import annotations

import numpy as np
import pytest

from domains.risk.services.balance.sources.readers.excel_reader import (
    ExcelSourceError,
    ExcelSourceReference,
    parse_cell_address,
    parse_excel_source,
    read_excel_source,
    read_excel_values,
    resolve_excel_path,
)


class TestParseExcelSource:
    """Tests for parse_excel_source function."""

    def test_valid_source(self):
        """Valid source format parses correctly."""
        result = parse_excel_source("data.xlsx|Sheet1|A1:C3")
        assert result.filename == "data.xlsx"
        assert result.sheet_name == "Sheet1"
        assert result.range_address == "A1:C3"

    def test_valid_source_uppercase_extension(self):
        """Extension validation is case-insensitive."""
        result = parse_excel_source("data.XLSX|Sheet1|A1:B2")
        assert result.filename == "data.XLSX"

    def test_valid_source_mixed_case_extension(self):
        """Extension validation is case-insensitive."""
        result = parse_excel_source("data.XlSx|Sheet1|A1:B2")
        assert result.filename == "data.XlSx"

    def test_empty_string_rejected(self):
        """Empty source string is rejected."""
        with pytest.raises(ExcelSourceError, match="non-empty string"):
            parse_excel_source("")

    def test_none_rejected(self):
        """None source is rejected."""
        with pytest.raises(ExcelSourceError, match="non-empty string"):
            parse_excel_source(None)

    def test_missing_sheet_rejected(self):
        """Source with missing sheet component is rejected."""
        with pytest.raises(ExcelSourceError, match="expected 'file.xlsx"):
            parse_excel_source("data.xlsx|A1:C3")

    def test_missing_range_rejected(self):
        """Source with missing range component is rejected."""
        with pytest.raises(ExcelSourceError, match="expected 'file.xlsx"):
            parse_excel_source("data.xlsx|Sheet1")

    def test_too_many_parts_rejected(self):
        """Source with too many pipe-separated parts is rejected."""
        with pytest.raises(ExcelSourceError, match="expected 'file.xlsx"):
            parse_excel_source("data.xlsx|Sheet1|A1:C3|extra")

    def test_empty_filename_rejected(self):
        """Empty filename is rejected."""
        with pytest.raises(ExcelSourceError, match="filename cannot be empty"):
            parse_excel_source("|Sheet1|A1:C3")

    def test_empty_sheet_rejected(self):
        """Empty sheet name is rejected."""
        with pytest.raises(ExcelSourceError, match="sheet name cannot be empty"):
            parse_excel_source("data.xlsx||A1:C3")

    def test_empty_range_rejected(self):
        """Empty range is rejected."""
        with pytest.raises(ExcelSourceError, match="range cannot be empty"):
            parse_excel_source("data.xlsx|Sheet1|")

    def test_path_separator_in_filename_rejected(self):
        """Filename with path separator is rejected."""
        with pytest.raises(ExcelSourceError, match="path separators"):
            parse_excel_source("subdir/data.xlsx|Sheet1|A1:C3")

    def test_backslash_in_filename_rejected(self):
        """Filename with backslash is rejected."""
        with pytest.raises(ExcelSourceError, match="path separators"):
            parse_excel_source("subdir\\data.xlsx|Sheet1|A1:C3")

    def test_dotdot_in_filename_rejected(self):
        """Filename with .. is rejected."""
        with pytest.raises(ExcelSourceError, match="cannot contain '..'"):
            parse_excel_source("../data.xlsx|Sheet1|A1:C3")

    def test_non_xlsx_extension_rejected(self):
        """Non-.xlsx extension is rejected."""
        with pytest.raises(ExcelSourceError, match="must have .xlsx extension"):
            parse_excel_source("data.xls|Sheet1|A1:C3")

    def test_no_extension_rejected(self):
        """Filename without extension is rejected."""
        with pytest.raises(ExcelSourceError, match="must have .xlsx extension"):
            parse_excel_source("data|Sheet1|A1:C3")

    def test_whitespace_trimmed(self):
        """Whitespace in components is trimmed."""
        result = parse_excel_source("  data.xlsx  |  Sheet1  |  A1:C3  ")
        assert result.filename == "data.xlsx"
        assert result.sheet_name == "Sheet1"
        assert result.range_address == "A1:C3"


class TestResolveExcelPath:
    """Tests for resolve_excel_path function."""

    def test_valid_path_resolution(self, tmp_path):
        """Valid path resolves correctly."""
        base_dir = tmp_path / "documents"
        base_dir.mkdir()

        result = resolve_excel_path(str(base_dir), "data.xlsx")
        assert result == base_dir / "data.xlsx"

    def test_empty_base_path_rejected(self):
        """Empty base documents path is rejected."""
        with pytest.raises(ExcelSourceError, match="APP_LOC_DOCUMENTS"):
            resolve_excel_path("", "data.xlsx")

    def test_path_traversal_rejected(self, tmp_path):
        """Path that escapes documents directory is rejected."""
        base_dir = tmp_path / "documents"
        base_dir.mkdir()

        with pytest.raises(ExcelSourceError, match="escapes documents directory"):
            # Try to escape to parent
            resolve_excel_path(str(base_dir), "../data.xlsx")

    def test_absolute_path_in_filename_rejected(self, tmp_path):
        """Absolute path in filename is rejected."""
        base_dir = tmp_path / "documents"
        base_dir.mkdir()

        # The parse_excel_source function should catch this, but resolve_excel_path
        # also validates containment
        with pytest.raises(ExcelSourceError):
            resolve_excel_path(str(base_dir), "/etc/passwd.xlsx")


class TestParseCellAddress:
    """Tests for parse_cell_address function."""

    def test_single_letter_column(self):
        """Single-letter column parses correctly."""
        col, row = parse_cell_address("A1")
        assert col == 1
        assert row == 1

    def test_multi_letter_column(self):
        """Multi-letter column parses correctly."""
        col, row = parse_cell_address("AA1")
        assert col == 27
        assert row == 1

    def test_triple_letter_column(self):
        """Triple-letter column parses correctly."""
        col, row = parse_cell_address("AAA1")
        assert col == 703
        assert row == 1

    def test_case_insensitive(self):
        """Cell address parsing is case-insensitive."""
        col1, row1 = parse_cell_address("a1")
        col2, row2 = parse_cell_address("A1")
        assert col1 == col2
        assert row1 == row2

    def test_invalid_address_rejected(self):
        """Invalid cell address is rejected."""
        with pytest.raises(ValueError, match="Invalid cell address"):
            parse_cell_address("1A")

    def test_numeric_only_rejected(self):
        """Numeric-only address is rejected."""
        with pytest.raises(ValueError, match="Invalid cell address"):
            parse_cell_address("123")

    def test_letters_only_rejected(self):
        """Letters-only address is rejected."""
        with pytest.raises(ValueError, match="Invalid cell address"):
            parse_cell_address("ABC")


class TestReadExcelValues:
    """Tests for read_excel_values function."""

    @pytest.fixture
    def sample_workbook(self, tmp_path):
        """Create a sample Excel workbook for testing."""
        pytest.importorskip("openpyxl")
        from openpyxl import Workbook

        wb = Workbook()
        ws = wb.active
        ws.title = "Sheet1"

        # Create a 2x3 range with numeric values
        ws["A1"] = 1.0
        ws["B1"] = 2.0
        ws["C1"] = 3.0
        ws["A2"] = 4.0
        ws["B2"] = 5.0
        ws["C2"] = 6.0

        file_path = tmp_path / "test.xlsx"
        wb.save(file_path)
        return file_path

    def test_valid_numeric_range(self, sample_workbook):
        """Valid numeric range reads correctly in row-major order."""
        result = read_excel_values(sample_workbook, "Sheet1", "A1:C2")
        expected = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0])
        np.testing.assert_array_equal(result, expected)

    def test_single_cell(self, sample_workbook):
        """Single cell range reads correctly."""
        result = read_excel_values(sample_workbook, "Sheet1", "A1")
        expected = np.array([1.0])
        np.testing.assert_array_equal(result, expected)

    def test_row_major_order(self, sample_workbook):
        """Values are returned in row-major order (left-to-right, top-to-bottom)."""
        result = read_excel_values(sample_workbook, "Sheet1", "A1:C2")
        # Row 1: 1, 2, 3
        # Row 2: 4, 5, 6
        assert result[0] == 1.0
        assert result[1] == 2.0
        assert result[2] == 3.0
        assert result[3] == 4.0
        assert result[4] == 5.0
        assert result[5] == 6.0

    def test_missing_sheet_rejected(self, sample_workbook):
        """Missing sheet is rejected."""
        with pytest.raises(ExcelSourceError, match="not found"):
            read_excel_values(sample_workbook, "NonExistent", "A1:C2")

    def test_empty_cell_rejected(self, tmp_path):
        """Empty cell is rejected."""
        pytest.importorskip("openpyxl")
        from openpyxl import Workbook

        wb = Workbook()
        ws = wb.active
        ws["A1"] = 1.0
        ws["B1"] = None  # Empty cell

        file_path = tmp_path / "test.xlsx"
        wb.save(file_path)

        with pytest.raises(ExcelSourceError, match="Empty cell"):
            read_excel_values(file_path, "Sheet", "A1:B1")

    def test_string_cell_rejected(self, tmp_path):
        """String cell is rejected."""
        pytest.importorskip("openpyxl")
        from openpyxl import Workbook

        wb = Workbook()
        ws = wb.active
        ws["A1"] = 1.0
        ws["B1"] = "text"

        file_path = tmp_path / "test.xlsx"
        wb.save(file_path)

        with pytest.raises(ExcelSourceError, match="String value"):
            read_excel_values(file_path, "Sheet", "A1:B1")

    def test_boolean_cell_rejected(self, tmp_path):
        """Boolean cell is rejected."""
        pytest.importorskip("openpyxl")
        from openpyxl import Workbook

        wb = Workbook()
        ws = wb.active
        ws["A1"] = 1.0
        ws["B1"] = True

        file_path = tmp_path / "test.xlsx"
        wb.save(file_path)

        with pytest.raises(ExcelSourceError, match="Boolean value"):
            read_excel_values(file_path, "Sheet", "A1:B1")

    def test_nan_cell_rejected(self, tmp_path):
        """NaN value is rejected (openpyxl round-trips NaN as empty cell)."""
        pytest.importorskip("openpyxl")
        from openpyxl import Workbook

        wb = Workbook()
        ws = wb.active
        ws["A1"] = float("nan")

        file_path = tmp_path / "test.xlsx"
        wb.save(file_path)

        with pytest.raises(ExcelSourceError, match="Empty|Non-finite"):
            read_excel_values(file_path, "Sheet", "A1")

    def test_infinity_cell_rejected(self, tmp_path):
        """Infinity value is rejected (openpyxl round-trips infinity as empty cell)."""
        pytest.importorskip("openpyxl")
        from openpyxl import Workbook

        wb = Workbook()
        ws = wb.active
        ws["A1"] = float("inf")

        file_path = tmp_path / "test.xlsx"
        wb.save(file_path)

        with pytest.raises(ExcelSourceError, match="Empty|Non-finite"):
            read_excel_values(file_path, "Sheet", "A1")

    def test_no_5000_value_limit(self, tmp_path):
        """Ranges with more than 5000 values are accepted."""
        pytest.importorskip("openpyxl")
        from openpyxl import Workbook

        wb = Workbook()
        ws = wb.active

        # Create a 100x60 range (6000 values); column 60 = BH
        for row in range(1, 101):
            for col in range(1, 61):
                ws.cell(row=row, column=col, value=float(row * col))

        file_path = tmp_path / "test.xlsx"
        wb.save(file_path)

        result = read_excel_values(file_path, "Sheet", "A1:BH100")
        assert len(result) == 6000
        assert result[0] == 1.0  # First value
        assert result[-1] == 6000.0  # Last value


class TestReadExcelSource:
    """Tests for read_excel_source function."""

    @pytest.fixture
    def sample_environment(self, tmp_path):
        """Create a sample environment with documents and Excel file."""
        pytest.importorskip("openpyxl")
        from openpyxl import Workbook

        # Create directory structure
        base_dir = tmp_path / "documents"
        base_dir.mkdir()

        # Create Excel file
        wb = Workbook()
        ws = wb.active
        ws.title = "Data"
        ws["A1"] = 10.0
        ws["B1"] = 20.0
        ws["A2"] = 30.0
        ws["B2"] = 40.0

        file_path = base_dir / "data.xlsx"
        wb.save(file_path)

        return {
            "base_path": str(base_dir),
            "file_path": file_path,
        }

    def test_valid_source_read(self, sample_environment):
        """Valid Excel source reads correctly."""
        result = read_excel_source(
            sample_environment["base_path"],
            "data.xlsx|Data|A1:B2",
        )
        expected = np.array([10.0, 20.0, 30.0, 40.0])
        np.testing.assert_array_equal(result, expected)

    def test_file_not_found(self, sample_environment):
        """Missing file is rejected."""
        with pytest.raises(ExcelSourceError, match="not found"):
            read_excel_source(
                sample_environment["base_path"],
                "nonexistent.xlsx|Data|A1:B2",
            )

    def test_invalid_source_format(self, sample_environment):
        """Invalid source format is rejected."""
        with pytest.raises(ExcelSourceError, match="expected 'file.xlsx"):
            read_excel_source(
                sample_environment["base_path"],
                "invalid_format",
            )

    def test_empty_environment_variable(self, sample_environment):
        """Empty base documents path is rejected."""
        with pytest.raises(ExcelSourceError, match="APP_LOC_DOCUMENTS"):
            read_excel_source(
                "",
                "data.xlsx|Data|A1:B2",
            )


class TestExcelSourceReference:
    """Tests for ExcelSourceReference dataclass."""

    def test_str_representation(self):
        """String representation is correct."""
        ref = ExcelSourceReference(
            filename="data.xlsx",
            sheet_name="Sheet1",
            range_address="A1:C3",
        )
        assert str(ref) == "data.xlsx|Sheet1|A1:C3"

    def test_frozen(self):
        """Reference is immutable (frozen)."""
        ref = ExcelSourceReference(
            filename="data.xlsx",
            sheet_name="Sheet1",
            range_address="A1:C3",
        )
        with pytest.raises(AttributeError):
            ref.filename = "other.xlsx"
