from pathlib import Path
from unittest.mock import Mock

import pandas as pd
import pytest
from gp134.tools.storage_lib import LocalBackend, StorageFS

from domains.risk.services.mcmf_catalog import McmfCatalogService
from infrastructure.files.filestore_registry import FileStoreRegistry


def test_mcmf_catalog_service_returns_simulation_sets_with_direct_parquet_files(
    tmp_path: Path,
) -> None:
    registry = _make_local_registry(tmp_path)
    base = (
        tmp_path
        / "simulation_source"
        / "mcmf"
        / "observation_date=20260101"
        / "operation_id=stress"
    )
    (base / "nested").mkdir(parents=True)
    (base / "brent.parquet").write_text("", encoding="utf-8")
    (base / "ttf.parquet").write_text("", encoding="utf-8")
    (base / "nested" / "ignored.parquet").write_text("", encoding="utf-8")

    response = McmfCatalogService(registry).list_catalog()

    assert [item.key for item in response.simulations] == ["20260101/stress"]
    assert [file.name for file in response.simulations[0].parquet_files] == [
        "brent.parquet",
        "ttf.parquet",
    ]


def test_mcmf_selected_file_aggregation_returns_yearly_summary_and_per_simulation_rows(
    tmp_path: Path,
) -> None:
    registry = _make_local_registry(tmp_path)
    base = (
        tmp_path
        / "simulation_source"
        / "mcmf"
        / "observation_date=20260101"
        / "operation_id=stress"
    )
    base.mkdir(parents=True)
    parquet_path = base / "brent.parquet"
    pd.DataFrame(
        {
            "time_index": ["2026-01-01", "2026-07-01", "2027-01-01"],
            "sim_0": [10.0, 30.0, 50.0],
            "sim_1": [20.0, 40.0, 70.0],
        }
    ).to_parquet(parquet_path)

    response = McmfCatalogService(registry).aggregate_selected_file(
        "observation_date=20260101/operation_id=stress/brent.parquet"
    )

    assert response.file.name == "brent.parquet"
    assert response.load_datetime is not None
    assert response.date_column == "time_index"
    assert response.simulation_columns == ["sim_0", "sim_1"]
    assert [(row.year, row.avg, row.med, row.simulation_count) for row in response.yearly] == [
        (2026, 25.0, 25.0, 2),
        (2027, 60.0, 60.0, 2),
    ]
    assert [
        (row.year, row.simulation, row.avg, row.med) for row in response.per_simulation_yearly
    ] == [
        (2026, "sim_0", 20.0, 20.0),
        (2026, "sim_1", 30.0, 30.0),
        (2027, "sim_0", 50.0, 50.0),
        (2027, "sim_1", 70.0, 70.0),
    ]


def test_mcmf_selected_file_rejects_invalid_relative_path(tmp_path: Path) -> None:
    registry = _make_local_registry(tmp_path)

    with pytest.raises(ValueError, match="MCMF parquet path"):
        McmfCatalogService(registry).aggregate_selected_file("../secret.parquet")


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
