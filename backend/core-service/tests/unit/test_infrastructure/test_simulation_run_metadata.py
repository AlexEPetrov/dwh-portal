import datetime as dt

import infrastructure.files.filestore_registry as filestore_registry
from api.valuation.results import get_simulation_run_metadata
from domains.risk.services.simulation_run_metadata import SimulationRunMetadataService
from infrastructure.files.filestore_registry import get_file_store_registry


def test_simulation_run_metadata_persists_resolved_source_path(tmp_path, monkeypatch):
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

    registry = get_file_store_registry()
    source_path = (
        registry.simulation_source / "executions/mcmf/observation_date=20260709/operation_id=eod"
    )

    service = SimulationRunMetadataService()
    saved = service.save(
        observation_date=dt.date(2026, 7, 10),
        valuation_type="eod",
        run_mode="simulation",
        request_id="request-1",
        requested_operation_id="eod",
        resolved_source_path=source_path,
    )
    loaded = service.load(
        observation_date=dt.date(2026, 7, 10), valuation_type="eod", run_mode="simulation"
    )

    assert loaded == saved
    assert loaded is not None
    assert loaded.simulation_source.requested_operation_id == "eod"
    assert loaded.simulation_source.resolved_path.endswith(
        "executions/mcmf/observation_date=20260709/operation_id=eod"
    )
    assert loaded.curve_resolution_policy.canonical_first is True
    assert loaded.curve_resolution_policy.manifest_policy == "immutable"


def test_simulation_run_metadata_endpoint_returns_operation_id(tmp_path, monkeypatch):
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

    registry = get_file_store_registry()
    source_path = (
        registry.simulation_source
        / "executions/mcmf/observation_date=20260709/operation_id=stress-eod"
    )
    SimulationRunMetadataService().save(
        observation_date=dt.date(2026, 7, 10),
        valuation_type="eod",
        run_mode="simulation",
        request_id="request-2",
        requested_operation_id="stress-eod",
        resolved_source_path=source_path,
    )

    response = get_simulation_run_metadata(
        observation_date=dt.date(2026, 7, 10),
        valuation_type="eod",
        run_mode="simulation",
    )

    assert response.request_id == "request-2"
    assert response.requested_operation_id == "stress-eod"
    assert response.resolved_source_path is not None
    assert response.resolved_source_path.endswith(
        "executions/mcmf/observation_date=20260709/operation_id=stress-eod"
    )
