import datetime as dt

import infrastructure.files.filestore_registry as filestore_registry
from domains.risk.services.balance.persistence.tree_save_metadata import (
    BalanceTreeSaveMetadataService,
)
from infrastructure.files.filestore_registry import get_file_store_registry


def _configure_filestore(tmp_path, monkeypatch):
    filestore_registry._file_store_registry_instance = None
    monkeypatch.setenv("APP_LOC_STORAGE_ROOT", str(tmp_path))
    monkeypatch.setenv("APP_LOC_LOAD_FILES_PATH", str(tmp_path / "load_files"))
    monkeypatch.setenv("APP_LOC_ARCHIVE_PATH", str(tmp_path / "archive"))
    monkeypatch.setenv("APP_LOC_TEMP_PATH", str(tmp_path / "tmp"))
    monkeypatch.setenv("APP_LOC_REPOSITORY_PATH", str(tmp_path / "repository"))
    monkeypatch.setenv("APP_LOC_EXECUTION_PRESETS_PATH", str(tmp_path / "execution_presets"))
    monkeypatch.setenv("APP_LOC_SIMULATION_SOURCE_ROOT", str(tmp_path / "simulation_source"))
    monkeypatch.setenv("APP_LOC_SIMULATION_SOURCE_PATH", "executions/mcmf")
    monkeypatch.setenv("APP_LOC_SIMULATION_TARGET_ROOT", str(tmp_path))
    monkeypatch.setenv("APP_LOC_SIMULATION_TARGET_PATH", "")
    monkeypatch.setenv("APP_LOC_VALUATION_TARGET_ROOT", str(tmp_path / "valuation"))
    monkeypatch.setenv("APP_LOC_VALUATION_TARGET_PATH", "")
    monkeypatch.setenv("APP_LOC_BALANCE_DATA_ROOT", str(tmp_path / "balance_data"))


def test_balance_tree_save_metadata_round_trips_by_valuation_year(tmp_path, monkeypatch):
    _configure_filestore(tmp_path, monkeypatch)

    service = BalanceTreeSaveMetadataService()
    saved = service.save(
        observation_date=dt.date(2026, 6, 15),
        valuation_type="custom1",
        valuation_year=2026,
        balance_tree_slug="balance2026_v2",
        balance_tree_name="Balance 2026 v2",
        static_files_written=3,
    )

    loaded = service.load(
        observation_date=dt.date(2026, 6, 15),
        valuation_type="custom1",
        valuation_year=2026,
    )

    assert loaded == saved
    assert loaded is not None
    assert loaded.balance_tree_slug == "balance2026_v2"
    assert loaded.valuation_year == 2026
    assert loaded.valuation_type == "custom1"
    assert loaded.static_files_written == 3


def test_balance_tree_save_metadata_coverage_reports_missing_years(tmp_path, monkeypatch):
    _configure_filestore(tmp_path, monkeypatch)

    service = BalanceTreeSaveMetadataService()
    service.save(
        observation_date=dt.date(2026, 6, 15),
        valuation_type="eod",
        valuation_year=2026,
        balance_tree_slug="balance2026",
        balance_tree_name="Balance 2026",
        static_files_written=1,
    )

    coverage = service.coverage(
        observation_date=dt.date(2026, 6, 15),
        valuation_type="eod",
        year_from=2026,
        year_to=2027,
    )

    assert [item.valuation_year for item in coverage.items] == [2026]
    assert coverage.missing_years == [2027]


def test_balance_tree_metadata_path_is_near_static_valuation_year_partition(tmp_path, monkeypatch):
    _configure_filestore(tmp_path, monkeypatch)
    registry = get_file_store_registry()

    path = registry.fact_simulation_balance_tree_metadata_path(
        observation_date=dt.date(2026, 6, 15),
        valuation_type="eod",
        valuation_year=2026,
    )

    assert "fact_simulation/observation_date=20260615/run_mode=static" in path.path
    assert "valuation_type=eod/valuation_year=2026/_balance_tree_metadata.json" in path.path
