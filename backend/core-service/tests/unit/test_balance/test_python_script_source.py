"""Tests for Python script source functionality in balance calculations."""

import datetime as dt
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from domains.management.models.gl_tree import GlTreeModel
from domains.risk.services.balance.sources.readers.python_script_reader import (
    PythonScriptContext,
    PythonScriptError,
    load_and_execute_script,
    resolve_script_path,
)


class TestResolveScriptPath:
    """Tests for resolve_script_path function."""

    def test_valid_script_path(self, tmp_path: Path):
        """Valid script file in documents directory resolves correctly."""
        script_file = tmp_path / "calculate_balance.py"
        script_file.write_text("def calculate_node(context): return 100.0")

        result = resolve_script_path(str(tmp_path), "calculate_balance.py")
        assert result == script_file
        assert result.is_file()

    def test_script_not_found(self, tmp_path: Path):
        """Missing script file raises PythonScriptError."""
        with pytest.raises(PythonScriptError, match="python:// script not found"):
            resolve_script_path(str(tmp_path), "nonexistent.py")

    def test_empty_filename(self, tmp_path: Path):
        """Empty filename raises PythonScriptError."""
        with pytest.raises(PythonScriptError, match="non-empty filename"):
            resolve_script_path(str(tmp_path), "")

    def test_whitespace_filename(self, tmp_path: Path):
        """Whitespace-only filename raises PythonScriptError."""
        with pytest.raises(PythonScriptError, match="non-empty filename"):
            resolve_script_path(str(tmp_path), "   ")

    def test_path_separator_rejected(self, tmp_path: Path):
        """Filenames with path separators are rejected."""
        with pytest.raises(PythonScriptError, match="path separators"):
            resolve_script_path(str(tmp_path), "subdir/script.py")

    def test_path_traversal_rejected(self, tmp_path: Path):
        """Path traversal attempts are rejected."""
        with pytest.raises(PythonScriptError, match="path separators"):
            resolve_script_path(str(tmp_path), "../script.py")

    def test_absolute_path_rejected(self, tmp_path: Path):
        """Absolute paths are rejected."""
        with pytest.raises(PythonScriptError, match="path separators"):
            resolve_script_path(str(tmp_path), "/absolute/path/script.py")

    def test_non_python_extension_rejected(self, tmp_path: Path):
        """Non-.py file extensions are rejected."""
        txt_file = tmp_path / "script.txt"
        txt_file.write_text("not a python script")

        with pytest.raises(PythonScriptError, match="must have .py extension"):
            resolve_script_path(str(tmp_path), "script.txt")

    def test_case_insensitive_extension(self, tmp_path: Path):
        """Extension validation is case-insensitive (.PY works)."""
        script_file = tmp_path / "script.PY"
        script_file.write_text("def calculate_node(context): return 1.0")

        result = resolve_script_path(str(tmp_path), "script.PY")
        assert result == script_file

    def test_empty_documents_path(self):
        """Empty documents path raises PythonScriptError."""
        with pytest.raises(PythonScriptError, match="APP_LOC_DOCUMENTS is not configured"):
            resolve_script_path("", "script.py")

    def test_whitespace_documents_path(self):
        """Whitespace-only documents path raises PythonScriptError (script not found)."""
        with pytest.raises(PythonScriptError, match="script not found"):
            resolve_script_path("   ", "script.py")


class TestLoadAndExecuteScript:
    """Tests for load_and_execute_script function."""

    def test_valid_script_float_return(self, tmp_path: Path):
        """Script returning float executes successfully."""
        script_file = tmp_path / "valid.py"
        script_file.write_text("def calculate_node(context): return 42.5")

        context = MagicMock(spec=PythonScriptContext)
        result = load_and_execute_script(script_file, context)
        assert result == 42.5

    def test_valid_script_int_return(self, tmp_path: Path):
        """Script returning int is coerced to float."""
        script_file = tmp_path / "valid.py"
        script_file.write_text("def calculate_node(context): return 100")

        context = MagicMock(spec=PythonScriptContext)
        result = load_and_execute_script(script_file, context)
        assert result == 100.0
        assert isinstance(result, float)

    def test_missing_calculate_node(self, tmp_path: Path):
        """Script without calculate_node function raises error."""
        script_file = tmp_path / "no_function.py"
        script_file.write_text("def other_function(): pass")

        context = MagicMock(spec=PythonScriptContext)
        with pytest.raises(PythonScriptError, match="does not define.*calculate_node"):
            load_and_execute_script(script_file, context)

    def test_script_raises_exception(self, tmp_path: Path):
        """Script that raises exception is caught and re-raised."""
        script_file = tmp_path / "error.py"
        script_file.write_text("def calculate_node(context): raise ValueError('Script error')")

        context = MagicMock(spec=PythonScriptContext)
        with pytest.raises(PythonScriptError, match="calculate_node.*raised an exception"):
            load_and_execute_script(script_file, context)

    def test_script_returns_string(self, tmp_path: Path):
        """Script returning non-numeric type raises error."""
        script_file = tmp_path / "string_return.py"
        script_file.write_text("def calculate_node(context): return 'not a number'")

        context = MagicMock(spec=PythonScriptContext)
        with pytest.raises(PythonScriptError, match="returned invalid.*type"):
            load_and_execute_script(script_file, context)

    def test_script_returns_none_coerced_to_zero(self, tmp_path: Path):
        """Script returning None is coerced to 0.0."""
        script_file = tmp_path / "none_return.py"
        script_file.write_text("def calculate_node(context): return None")

        context = MagicMock(spec=PythonScriptContext)
        result = load_and_execute_script(script_file, context)
        assert result == 0.0
        assert isinstance(result, float)

    def test_script_returns_list(self, tmp_path: Path):
        """Script returning list is converted to numpy.ndarray."""
        script_file = tmp_path / "list_return.py"
        script_file.write_text("def calculate_node(context): return [1.0, 2.0, 3.0]")

        context = MagicMock(spec=PythonScriptContext)
        result = load_and_execute_script(script_file, context)
        import numpy as np

        assert isinstance(result, np.ndarray)
        assert result.tolist() == [1.0, 2.0, 3.0]

    def test_script_returns_tuple(self, tmp_path: Path):
        """Script returning tuple is converted to numpy.ndarray."""
        script_file = tmp_path / "tuple_return.py"
        script_file.write_text("def calculate_node(context): return (10.0, 20.0)")

        context = MagicMock(spec=PythonScriptContext)
        result = load_and_execute_script(script_file, context)
        import numpy as np

        assert isinstance(result, np.ndarray)
        assert result.tolist() == [10.0, 20.0]

    def test_script_returns_numpy_array(self, tmp_path: Path):
        """Script returning numpy.ndarray passes through."""
        script_file = tmp_path / "array_return.py"
        script_file.write_text(
            "import numpy as np\ndef calculate_node(context): return np.array([5.0, 6.0, 7.0])"
        )

        context = MagicMock(spec=PythonScriptContext)
        result = load_and_execute_script(script_file, context)
        import numpy as np

        assert isinstance(result, np.ndarray)
        assert result.tolist() == [5.0, 6.0, 7.0]

    def test_script_returns_empty_list_rejected(self, tmp_path: Path):
        """Script returning empty list raises error."""
        script_file = tmp_path / "empty_list.py"
        script_file.write_text("def calculate_node(context): return []")

        context = MagicMock(spec=PythonScriptContext)
        with pytest.raises(PythonScriptError, match="empty array"):
            load_and_execute_script(script_file, context)

    def test_script_returns_array_with_nan_rejected(self, tmp_path: Path):
        """Script returning array with NaN raises error."""
        script_file = tmp_path / "nan_array.py"
        script_file.write_text(
            "import numpy as np\ndef calculate_node(context): return np.array([1.0, float('nan')])"
        )

        context = MagicMock(spec=PythonScriptContext)
        with pytest.raises(PythonScriptError, match="non-finite"):
            load_and_execute_script(script_file, context)

    def test_script_returns_array_with_inf_rejected(self, tmp_path: Path):
        """Script returning array with inf raises error."""
        script_file = tmp_path / "inf_array.py"
        script_file.write_text(
            "import numpy as np\ndef calculate_node(context): return np.array([1.0, float('inf')])"
        )

        context = MagicMock(spec=PythonScriptContext)
        with pytest.raises(PythonScriptError, match="non-finite"):
            load_and_execute_script(script_file, context)

    def test_script_returns_2d_array_rejected(self, tmp_path: Path):
        """Script returning 2D numpy array raises error."""
        script_file = tmp_path / "2d_array.py"
        script_file.write_text(
            "import numpy as np\ndef calculate_node(context): return np.array([[1.0, 2.0], [3.0, 4.0]])"
        )

        context = MagicMock(spec=PythonScriptContext)
        with pytest.raises(PythonScriptError, match="2D array"):
            load_and_execute_script(script_file, context)

    def test_script_returns_bool_rejected(self, tmp_path: Path):
        """Script returning bool raises error (bool is a subclass of int but rejected explicitly)."""
        script_file = tmp_path / "bool_return.py"
        script_file.write_text("def calculate_node(context): return True")

        context = MagicMock(spec=PythonScriptContext)
        with pytest.raises(PythonScriptError, match="bool"):
            load_and_execute_script(script_file, context)

    def test_script_returns_nan_rejected(self, tmp_path: Path):
        """Script returning NaN raises error."""
        script_file = tmp_path / "nan_return.py"
        script_file.write_text("def calculate_node(context): return float('nan')")

        context = MagicMock(spec=PythonScriptContext)
        with pytest.raises(PythonScriptError, match="NaN"):
            load_and_execute_script(script_file, context)

    def test_script_syntax_error(self, tmp_path: Path):
        """Script with syntax error raises PythonScriptError."""
        script_file = tmp_path / "syntax_error.py"
        script_file.write_text("def calculate_node(context) return 1.0")  # Missing colon

        context = MagicMock(spec=PythonScriptContext)
        with pytest.raises(PythonScriptError, match="Failed to load python:// script"):
            load_and_execute_script(script_file, context)

    def test_script_import_error(self, tmp_path: Path):
        """Script with import error raises PythonScriptError."""
        script_file = tmp_path / "import_error.py"
        script_file.write_text("import nonexistent_module\ndef calculate_node(context): return 1.0")

        context = MagicMock(spec=PythonScriptContext)
        with pytest.raises(PythonScriptError, match="Failed to load python:// script"):
            load_and_execute_script(script_file, context)

    def test_script_with_context_access(self, tmp_path: Path):
        """Script can access context fields correctly."""
        script_file = tmp_path / "context_access.py"
        script_file.write_text("""
def calculate_node(context):
    year = context.observation_date.year
    return float(year)
""")

        context = PythonScriptContext(
            observation_date=dt.date(2026, 1, 15),
            scenario="base",
            valuation_type="eod",
            balance_year=2026,
            tree=MagicMock(spec=GlTreeModel),
        )

        result = load_and_execute_script(script_file, context)
        assert result == 2026.0


class TestPythonScriptContext:
    """Tests for PythonScriptContext dataclass."""

    def test_context_creation(self):
        """Context can be created with all required fields."""
        tree = MagicMock(spec=GlTreeModel)
        context = PythonScriptContext(
            observation_date=dt.date(2026, 3, 15),
            scenario="stress",
            valuation_type="eod",
            balance_year=2026,
            tree=tree,
        )

        assert context.observation_date == dt.date(2026, 3, 15)
        assert context.scenario == "stress"
        assert context.valuation_type == "eod"
        assert context.balance_year == 2026
        assert context.tree is tree

    def test_context_with_none_scenario(self):
        """Context accepts None for scenario."""
        context = PythonScriptContext(
            observation_date=dt.date(2026, 1, 1),
            scenario=None,
            valuation_type="eod",
            balance_year=2026,
            tree=MagicMock(spec=GlTreeModel),
        )

        assert context.scenario is None

    def test_context_frozen(self):
        """Context is frozen (immutable)."""
        context = PythonScriptContext(
            observation_date=dt.date(2026, 1, 1),
            scenario="base",
            valuation_type="eod",
            balance_year=2026,
            tree=MagicMock(spec=GlTreeModel),
        )

        with pytest.raises(AttributeError):
            context.scenario = "modified"


class TestObjectUriManagerPythonScheme:
    """Tests for ObjectUriManager.parse_uri() with python:// URIs (task 7.2)."""

    def test_parse_python_uri_correct(self):
        """Parse correct python:// URI."""
        from domains.risk.services.object_uri_manager import ObjectUriManager

        parsed = ObjectUriManager.parse_uri("python://test_script.py")
        assert parsed is not None
        assert parsed.source == "python"
        assert parsed.path == "test_script.py"
        assert parsed.raw == "python://test_script.py"

    def test_parse_python_uri_with_complex_filename(self):
        """Parse python:// URI with underscores and numbers."""
        from domains.risk.services.object_uri_manager import ObjectUriManager

        parsed = ObjectUriManager.parse_uri("python://calculate_balance_2026.py")
        assert parsed is not None
        assert parsed.source == "python"
        assert parsed.path == "calculate_balance_2026.py"

    def test_parse_python_uri_empty_payload(self):
        """Parse python:// URI with empty payload (validation happens in resolve_script_path)."""
        from domains.risk.services.object_uri_manager import ObjectUriManager

        parsed = ObjectUriManager.parse_uri("python://")
        assert parsed is not None
        assert parsed.source == "python"
        assert parsed.path == ""

    def test_parse_python_uri_path_traversal(self):
        """Parse python:// URI with path traversal (validation happens in resolve_script_path)."""
        from domains.risk.services.object_uri_manager import ObjectUriManager

        parsed = ObjectUriManager.parse_uri("python://../script.py")
        assert parsed is not None
        assert parsed.source == "python"
        assert parsed.path == "../script.py"

    def test_parse_python_uri_with_directory(self):
        """Parse python:// URI with directory separator (validation happens in resolve_script_path)."""
        from domains.risk.services.object_uri_manager import ObjectUriManager

        parsed = ObjectUriManager.parse_uri("python://subdir/script.py")
        assert parsed is not None
        assert parsed.source == "python"
        assert parsed.path == "subdir/script.py"


class TestMonitoredPositionServicePythonUri:
    """Tests for MonitoredPositionService._resolve_python_uri() (task 7.3)."""

    def test_resolve_python_uri_success(self, tmp_path: Path, monkeypatch):
        """python:// URI resolves successfully with correct cell_source metadata."""
        from domains.risk.services.balance.cell import BalanceCellValue
        from domains.risk.services.balance.sources.monitored_balance_cell_resolver import (
            MonitoredPositionService,
        )

        script_file = tmp_path / "test_script.py"
        script_file.write_text("def calculate_node(context): return 42.5")

        # Mock LocationsSettings to return tmp_path as documents path
        class MockLocations:
            documents = str(tmp_path)

        monkeypatch.setattr("settings.location.LocationsSettings", lambda: MockLocations())

        from domains.risk.services.object_uri_manager import ParsedUri

        parsed = ParsedUri(source="python", path="test_script.py", raw="python://test_script.py")

        service = MonitoredPositionService.__new__(MonitoredPositionService)
        result = service._resolve_python_uri(
            parsed,
            observation_date=dt.date(2026, 1, 15),
            balance_year=2026,
            scenario="base",
            tree=MagicMock(spec=GlTreeModel),
        )

        assert isinstance(result, BalanceCellValue)
        assert result.value == 42.5
        assert result.cell_source == "python"
        assert result.scenario_mode == "deterministic"

    def test_resolve_python_uri_error_returns_none(self, tmp_path: Path, monkeypatch):
        """python:// URI error returns BalanceCellValue(None, 'none', 'deterministic')."""
        from domains.risk.services.balance.cell import BalanceCellValue
        from domains.risk.services.balance.sources.monitored_balance_cell_resolver import (
            MonitoredPositionService,
        )

        # Mock LocationsSettings to return tmp_path as documents path
        class MockLocations:
            documents = str(tmp_path)

        monkeypatch.setattr("settings.location.LocationsSettings", lambda: MockLocations())

        from domains.risk.services.object_uri_manager import ParsedUri

        # Use a non-existent script to trigger error
        parsed = ParsedUri(source="python", path="nonexistent.py", raw="python://nonexistent.py")

        service = MonitoredPositionService.__new__(MonitoredPositionService)
        result = service._resolve_python_uri(
            parsed,
            observation_date=dt.date(2026, 1, 15),
            balance_year=2026,
            scenario="base",
            tree=MagicMock(spec=GlTreeModel),
        )

        assert isinstance(result, BalanceCellValue)
        assert result.value is None
        assert result.cell_source == "none"
        assert result.scenario_mode == "deterministic"
