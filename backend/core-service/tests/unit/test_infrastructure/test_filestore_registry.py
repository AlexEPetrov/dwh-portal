"""Tests for FileStoreRegistry.simulation_source_path() resolution logic.

Covers the operation_id precedence rule:
- When operation_id is specified → scan ALL observation_date partitions
  to find the correct path, ignoring the request's observation_date.
- When operation_id is NOT specified → scan by observation_date for latest.
"""

import datetime as dt
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, Mock, patch

import pytest
from gp134.tools.storage_lib import LocalBackend, StorageFS

from infrastructure.files.filestore_registry import _OPERATION_ID_PATTERN, FileStoreRegistry

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_registry(**overrides: Any) -> FileStoreRegistry:
    """Create a FileStoreRegistry with mocked locations."""
    loc_settings = Mock()
    loc_settings.simulation_source_root = overrides.get(
        "simulation_source_root", "s3://bucket/simulation_source"
    )
    loc_settings.simulation_source_path = overrides.get(
        "simulation_source_path",
        "mcmf/observation_date={observation_date}/operation_id={operation_id}",
    )
    loc_settings.storage_root = "s3://bucket/storage"
    loc_settings.temp_path = "s3://bucket/temp"
    loc_settings.balance_data_root = None
    loc_settings.executions_path = "executions/data"

    with patch.object(FileStoreRegistry, "_create_storage") as mock_create:
        mock_storage = Mock()
        mock_storage.__truediv__ = lambda s, x: MagicMock(full_path=f"{s.full_path}/{x}")
        mock_storage.full_path = "s3://bucket/root"
        mock_create.return_value = mock_storage

        registry = FileStoreRegistry.__new__(FileStoreRegistry)
        registry._loc = loc_settings
        registry._s3 = Mock()
        registry.simulation_source = mock_storage
        registry.storage = mock_storage
        registry.temp_storage = mock_storage
        registry.balance_data_source = None
        return registry


# ---------------------------------------------------------------------------
# operation_id selector pattern tests
# ---------------------------------------------------------------------------


class TestOperationIdPattern:
    """Tests for the _OPERATION_ID_PATTERN regex."""

    @pytest.mark.parametrize(
        "operation_id_dir",
        [
            "operation_id=550e8400-e29b-41d4-a716-446655440000",
            "operation_id=6ba7b810-9dad-11d1-80b4-00c04fd430c8",
            "operation_id=f47ac10b-58cc-4372-a567-0e02b2c3d479",
            "operation_id=stress",
            "operation_id=stress-eod",
            "operation_id=crisis_2026.v1",
        ],
    )
    def test_pattern_matches_valid_selector(self, operation_id_dir: str) -> None:
        match = _OPERATION_ID_PATTERN.match(operation_id_dir)
        assert match is not None
        # Extract just the UUID part (without "operation_id=")
        extracted_uuid = operation_id_dir.replace("operation_id=", "")
        assert match.group(1) == extracted_uuid

    @pytest.mark.parametrize(
        "invalid_selector",
        [
            "not-a-uuid",
            "operation_id=",
            "operation_id=/stress",
            "operation_id=2026-01-01/stress",
            "operation_id=stress/eod",
            "operation_id= stress",
        ],
    )
    def test_pattern_rejects_invalid_selector(self, invalid_selector: str) -> None:
        match = _OPERATION_ID_PATTERN.match(invalid_selector)
        assert match is None


# ---------------------------------------------------------------------------
# Case A: operation_id specified — cross-partition scan
# ---------------------------------------------------------------------------


class TestSimulationSourcePathWithOperationId:
    """Test resolution when operation_id is explicitly provided."""

    def test_case_a_finds_operation_id_in_latest_observation_date(self) -> None:
        """operation_id exists under a recent observation_date → return that path."""
        registry = _make_registry()

        # Mock _list_child_directory_names to return observation_date partitions
        with patch.object(
            registry, "_list_child_directory_names", return_value=["observation_date=20260615"]
        ) as mock_list, patch.object(
            registry, "_scan_operation_ids", return_value=["aaa-bbb-ccc"]
        ) as mock_scan:
            params = {
                "observation_date": dt.date(2026, 6, 29),
                "operation_id": "aaa-bbb-ccc",
            }
            result = registry.simulation_source_path(params)

            assert result is not None
            mock_list.assert_called_once()
            mock_scan.assert_called_once()

    def test_case_a_operation_id_not_found_raises_error(self) -> None:
        """operation_id not found in any observation_date partition → ValueError."""
        registry = _make_registry()

        with patch.object(
            registry,
            "_list_child_directory_names",
            return_value=["observation_date=20260615", "observation_date=20260629"],
        ), patch.object(registry, "_scan_operation_ids", return_value=[]):
            params = {
                "observation_date": dt.date(2026, 6, 29),
                "operation_id": "nonexistent-uuid",
            }
            with pytest.raises(ValueError, match="operation_id=nonexistent-uuid not found"):
                registry.simulation_source_path(params)

    def test_case_a_finds_operation_id_in_older_observation_date(self) -> None:
        """Slug operation_id exists under an older observation_date — request obs_date is ignored."""
        registry = _make_registry(
            simulation_source_path="mcmf/observation_date={observation_date}/operation_id={operation_id}"
        )

        # Scan order is reverse (most recent first), so we return the alias only on the
        # last call (oldest partition). This verifies cross-partition scanning works.
        with patch.object(
            registry,
            "_list_child_directory_names",
            return_value=[
                "observation_date=20260601",
                "observation_date=20260615",
                "observation_date=20260629",
            ],
        ):
            call_counter = {"count": 0}

            def scan_side_effect(path: Any) -> list[str]:
                call_counter["count"] += 1
                # Return the alias only on the last call (oldest partition, scanned last)
                if call_counter["count"] == 3:
                    return ["stress"]
                return []

            with patch.object(registry, "_scan_operation_ids", side_effect=scan_side_effect):
                params = {
                    "observation_date": dt.date(2026, 6, 29),
                    "operation_id": "stress",
                }
                result = registry.simulation_source_path(params)
                assert result is not None

    def test_case_a_slug_operation_id_picks_latest_matching_partition_before_command_date(
        self,
    ) -> None:
        """Slug operation_id resolves to latest matching partition <= command observation_date."""
        registry = _make_registry()

        with patch.object(
            registry,
            "_list_child_directory_names",
            return_value=[
                "observation_date=20260601",
                "observation_date=20260615",
                "observation_date=20260629",
            ],
        ):
            call_counter = {"count": 0}

            def scan_side_effect(path: Any) -> list[str]:
                call_counter["count"] += 1
                if call_counter["count"] == 1:
                    return ["stress"]
                return []

            with patch.object(registry, "_scan_operation_ids", side_effect=scan_side_effect):
                result = registry.simulation_source_path(
                    {"observation_date": dt.date(2026, 6, 20), "operation_id": "stress"}
                )

        assert "observation_date=20260615" in result.full_path
        assert "operation_id=stress" in result.full_path

    def test_case_a_explicit_date_selector_can_pick_future_source(self) -> None:
        """Explicit YYYYMMDD/slug can select a source after command observation_date."""
        registry = _make_registry()

        with patch.object(registry, "_scan_operation_ids", return_value=["stress"]):
            result = registry.simulation_source_path(
                {"observation_date": dt.date(2026, 6, 1), "operation_id": "20260629/stress"}
            )

        assert "observation_date=20260629" in result.full_path
        assert "operation_id=stress" in result.full_path

    def test_case_a_uuid_operation_id_duplicate_raises_error(self) -> None:
        """UUID-like operation_id must be exact and unique across partitions."""
        registry = _make_registry()
        selector = "550e8400-e29b-41d4-a716-446655440000"

        with patch.object(
            registry,
            "_list_child_directory_names",
            return_value=["observation_date=20260615", "observation_date=20260629"],
        ), patch.object(registry, "_scan_operation_ids", return_value=[selector]):
            with pytest.raises(ValueError, match="found under multiple"):
                registry.simulation_source_path(
                    {"observation_date": dt.date(2026, 6, 1), "operation_id": selector}
                )

    def test_case_a_explicit_date_gated_selector(self) -> None:
        """operation_id='YYYY-MM-DD/slug' checks exact source date partition."""
        registry = _make_registry()

        with patch.object(registry, "_scan_operation_ids", return_value=["stress"]) as mock_scan:
            result = registry.simulation_source_path(
                {"observation_date": dt.date(2026, 6, 29), "operation_id": "2026-01-01/stress"}
            )

        assert "observation_date=20260101" in result.full_path
        assert "operation_id=stress" in result.full_path
        mock_scan.assert_called_once()

    def test_case_a_no_observation_date_partitions_raises_clear_error(self) -> None:
        """No observation_date partitions under scan base → clear error."""
        registry = _make_registry()

        with patch.object(registry, "_list_child_directory_names", return_value=[]):
            params = {
                "observation_date": dt.date(2026, 6, 29),
                "operation_id": "some-uuid",
            }
            with pytest.raises(ValueError, match="operation_id=some-uuid not found"):
                registry.simulation_source_path(params)


# ---------------------------------------------------------------------------
# Case B: operation_id NOT specified — scan by observation_date (existing)
# ---------------------------------------------------------------------------


class TestSimulationSourcePathWithoutOperationId:
    """Test resolution when operation_id is NOT provided."""

    def test_case_b_scans_observation_date_for_latest(self) -> None:
        """No operation_id → scan observation_date=X/ for latest UUID."""
        registry = _make_registry()

        with patch.object(
            registry, "_list_child_directory_names", return_value=["observation_date=20260629"]
        ), patch.object(
            registry, "_scan_operation_ids", return_value=["uuid7-a", "uuid7-b", "uuid7-c"]
        ):
            params = {
                "observation_date": dt.date(2026, 6, 29),
            }
            result = registry.simulation_source_path(params)
            assert result is not None

    def test_case_b_no_candidates_raises_error(self) -> None:
        """No operation_id directories in any observation_date → ValueError."""
        registry = _make_registry()

        with patch.object(registry, "_scan_operation_ids", return_value=[]):
            params = {
                "observation_date": dt.date(2026, 6, 29),
            }
            with pytest.raises(
                ValueError, match="No operation_id directories found in any observation_date"
            ):
                registry.simulation_source_path(params)

    def test_case_b_skips_operation_id_after_requested_observation_date(self) -> None:
        """No operation_id → pick latest source date <= command observation_date."""
        registry = _make_registry()

        with patch.object(
            registry,
            "_list_child_directory_names",
            return_value=[
                "other_folder",
                "observation_date=20260601",
                "observation_date=20260615",
                "observation_date=20260629",
                "observation_date=20260713",  # AFTER the requested date
            ],
        ):
            call_order = {"count": 0}

            def scan_side_effect(path: Any) -> list[str]:
                call_order["count"] += 1
                # Future partition 20260713 is filtered out. The first scanned partition is 20260629.
                if call_order["count"] == 1:
                    return ["op-b", "op-c", "op-a"]
                return []

            with patch.object(registry, "_scan_operation_ids", side_effect=scan_side_effect):
                params = {
                    "observation_date": dt.date(2026, 6, 29),
                }
                result = registry.simulation_source_path(params)
                assert result is not None
                assert "observation_date=20260629" in result.full_path
                assert "operation_id=op-c" in result.full_path

    def test_case_b_no_operation_id_pattern_in_template(self) -> None:
        """Template without {operation_id} → return as-is."""
        registry = _make_registry(simulation_source_path="mcmf/observation_date={observation_date}")

        params = {
            "observation_date": dt.date(2026, 6, 29),
        }
        result = registry.simulation_source_path(params)
        assert result is not None


class TestMcmfCatalogListing:
    """Tests for read-only MCMF catalog storage listing helpers."""

    def test_mcmf_catalog_lists_immediate_parquet_files_only(self, tmp_path: Path) -> None:
        registry = _make_local_registry(tmp_path)
        base = (
            tmp_path
            / "simulation_source"
            / "mcmf"
            / "observation_date=20260101"
            / "operation_id=stress"
        )
        nested = base / "nested"
        nested.mkdir(parents=True)
        (base / "brent.parquet").write_text("", encoding="utf-8")
        (base / "notes.txt").write_text("", encoding="utf-8")
        (nested / "ignored.parquet").write_text("", encoding="utf-8")

        files = registry.list_mcmf_catalog_parquet_files(
            "observation_date=20260101",
            "operation_id=stress",
        )

        assert [Path(file.full_path).name for file in files] == ["brent.parquet"]

    def test_mcmf_catalog_lists_observation_and_operation_partitions(self, tmp_path: Path) -> None:
        registry = _make_local_registry(tmp_path)
        root = tmp_path / "simulation_source" / "mcmf"
        (root / "observation_date=20260101" / "operation_id=stress").mkdir(parents=True)
        (root / "observation_date=20260102" / "operation_id=eod").mkdir(parents=True)

        observations = registry.list_mcmf_catalog_observation_partitions()
        operations = registry.list_mcmf_catalog_operation_partitions("observation_date=20260101")

        assert observations == ["observation_date=20260101", "observation_date=20260102"]
        assert operations == ["operation_id=stress"]


def _make_local_registry(tmp_path: Path) -> FileStoreRegistry:
    loc_settings = Mock()
    loc_settings.simulation_source_root = str(tmp_path / "simulation_source")
    loc_settings.simulation_source_path = (
        "mcmf/observation_date={observation_date}/operation_id={operation_id}"
    )
    loc_settings.storage_root = str(tmp_path / "storage")
    loc_settings.temp_path = str(tmp_path / "temp")
    loc_settings.balance_data_root = None
    loc_settings.executions_path = "executions/data"

    registry = FileStoreRegistry.__new__(FileStoreRegistry)
    registry._loc = loc_settings
    registry._s3 = Mock()
    registry.simulation_source = StorageFS(LocalBackend(), loc_settings.simulation_source_root)
    registry.storage = StorageFS(LocalBackend(), loc_settings.storage_root)
    registry.temp_storage = StorageFS(LocalBackend(), loc_settings.temp_path)
    registry.balance_data_source = None
    return registry


def _write_partition_file(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    (path / "part.parquet").write_bytes(b"parquet-placeholder")


def test_list_valuation_types_scopes_v8_partitions_by_date_and_run_mode(tmp_path: Path) -> None:
    registry = _make_local_registry(tmp_path)
    data_root = tmp_path / "storage" / "executions" / "data"
    observation = "observation_date=20260812"

    for valuation_type in ("eod", "Forecast 2027.01"):
        _write_partition_file(
            data_root
            / "fact_simulation"
            / observation
            / "run_mode=simulation"
            / f"valuation_type={valuation_type}"
            / "valuation_year=2027"
        )
    _write_partition_file(
        data_root
        / "fact_simulation"
        / observation
        / "run_mode=static"
        / "valuation_type=balance-custom"
        / "valuation_year=2027"
    )
    _write_partition_file(
        data_root
        / "fact_simulation"
        / "observation_date=20260811"
        / "run_mode=simulation"
        / "valuation_type=wrong-date"
    )

    observation_date = dt.date(2026, 8, 12)
    assert registry.list_valuation_types_for_observation(observation_date, "simulation") == [
        "Forecast 2027.01",
        "eod",
    ]
    assert registry.list_valuation_types_for_observation(observation_date, "static") == [
        "balance-custom"
    ]
    assert registry.list_simulation_hive_observation_partitions() == [
        "observation_date=20260811",
        "observation_date=20260812",
    ]


def test_fact_simulation_metadata_paths_share_date_first_cube(tmp_path: Path) -> None:
    registry = _make_local_registry(tmp_path)

    simulation_path = registry.fact_simulation_run_metadata_path(
        observation_date=dt.date(2026, 8, 12),
        valuation_type="eod",
        run_mode="simulation",
    )
    static_path = registry.fact_simulation_balance_tree_metadata_path(
        observation_date=dt.date(2026, 8, 12),
        valuation_type="eod",
        valuation_year=2027,
    )

    common_prefix = "fact_simulation/observation_date=20260812/"
    assert common_prefix + "run_mode=simulation/valuation_type=eod/_run_metadata.json" in (
        simulation_path.path
    )
    assert common_prefix + "run_mode=static/valuation_type=eod/" in static_path.path


def test_fact_paths_delegate_to_shared_builder(tmp_path: Path, monkeypatch) -> None:
    registry = _make_local_registry(tmp_path)
    glob_builder = MagicMock(
        return_value=(
            "fact_simulation/observation_date=20260401/run_mode=simulation/valuation_type=eod"
        )
    )
    discovery_builder = MagicMock(return_value="fact_simulation")
    monkeypatch.setattr(
        "infrastructure.files.filestore_registry.build_fact_glob_prefix", glob_builder
    )
    monkeypatch.setattr(
        "infrastructure.files.filestore_registry.observation_discovery_root", discovery_builder
    )

    registry.fact_simulation_glob(dt.date(2026, 4, 1), "eod")
    registry.list_simulation_hive_observation_partitions()

    glob_builder.assert_called_once_with(
        "",
        observation_date=dt.date(2026, 4, 1),
        run_mode="simulation",
        valuation_type="eod",
    )
    discovery_builder.assert_called_once_with("")


def test_list_valuation_types_reads_deterministic_layout(tmp_path: Path) -> None:
    registry = _make_local_registry(tmp_path)
    data_root = tmp_path / "storage" / "executions" / "data"
    observation = "observation_date=20260812"
    _write_partition_file(
        data_root
        / "fact_deterministic"
        / observation
        / "run_mode=deterministic"
        / "valuation_type=intraday"
    )
    assert registry.list_valuation_types_for_observation(dt.date(2026, 8, 12), "deterministic") == [
        "intraday",
    ]
