import datetime as dt
from unittest.mock import MagicMock

from gp134.tools.storage_lib import LocalBackend, StorageFS

from api.reporting.sql_query import _build_s3_path as build_api_s3_path
from domains.reporting.services.sql_query_service import FactQueryService
from infrastructure.analytics.duckdb_storage_adapter import DuckDbStorageAdapter
from settings.location import LocationsSettings
from settings.s3 import S3ConnectionSettings


def _locations(tmp_path, storage_root: str | None = None) -> LocationsSettings:
    return LocationsSettings(
        load_files_path=str(tmp_path / "load_files"),
        archive_path=str(tmp_path / "archive"),
        temp_path=str(tmp_path / "tmp"),
        repository_path=str(tmp_path / "repository"),
        simulation_source_root=str(tmp_path / "simulation_source"),
        simulation_source_path="",
        execution_presets_path=str(tmp_path / "execution_presets"),
        storage_root=storage_root or str(tmp_path / "storage"),
        executions_path="executions/data",
    )


def test_build_s3_path_uses_unified_run_mode_partition_order(tmp_path):
    service = FactQueryService(locations=_locations(tmp_path))

    path = service._build_s3_path(
        fact_slug="fact_simulation",
        observation_date="20260615",
        run_mode="simulation",
        valuation_type="eod",
    )

    assert path.endswith(
        "/executions/data/fact_simulation/observation_date=20260615/run_mode=simulation/valuation_type=eod/**/*.parquet"
    )


def test_build_s3_path_wildcards_run_mode_when_not_specified(tmp_path):
    service = FactQueryService(locations=_locations(tmp_path))

    path = service._build_s3_path(
        fact_slug="fact_simulation",
        observation_date="20260615",
        run_mode="",
        valuation_type="",
    )

    assert path.endswith(
        "/executions/data/fact_simulation/observation_date=20260615/run_mode=*/valuation_type=*/**/*.parquet"
    )


def test_shared_duckdb_glob_uses_date_first_cube_order(tmp_path):
    base_path = StorageFS(LocalBackend()).path(str(tmp_path / "fact_simulation"))
    adapter = DuckDbStorageAdapter(base_path)

    path = adapter.valuation_hive_path_glob(
        observation_date=dt.date(2026, 6, 15),
        run_mode="simulation",
        valuation_type="eod",
    )

    assert path.endswith(
        "/fact_simulation/observation_date=20260615/run_mode=simulation/valuation_type=eod/**/*.parquet"
    )


def test_shared_duckdb_glob_preserves_deterministic_cube_root(tmp_path):
    base_path = StorageFS(LocalBackend()).path(str(tmp_path / "fact_deterministic"))
    adapter = DuckDbStorageAdapter(base_path)

    path = adapter.valuation_hive_path_glob(
        observation_date=dt.date(2026, 8, 11),
        run_mode="deterministic",
        valuation_type="eod",
        filename="contracts.parquet",
    )

    assert path.endswith(
        "/fact_deterministic/observation_date=20260811/run_mode=deterministic/"
        "valuation_type=eod/**/contracts.parquet"
    )
    assert "fact_deterministic/fact_simulation" not in path


def test_reader_helpers_delegate_partition_order_to_shared_builder(monkeypatch, tmp_path):
    delegated = MagicMock(
        return_value=(
            "fact_simulation/observation_date=20260615/run_mode=simulation/valuation_type=eod"
        )
    )
    monkeypatch.setattr(
        "infrastructure.analytics.duckdb_storage_adapter.build_fact_glob_prefix", delegated
    )
    adapter = DuckDbStorageAdapter(StorageFS(LocalBackend()).path(str(tmp_path)))

    adapter.valuation_hive_path_glob(
        observation_date=dt.date(2026, 6, 15),
        run_mode="simulation",
        valuation_type="eod",
    )

    delegated.assert_called_once_with(
        str(tmp_path),
        observation_date=dt.date(2026, 6, 15),
        run_mode="simulation",
        valuation_type="eod",
    )


def test_api_sql_helper_uses_canonical_wildcard_positions(tmp_path):
    path = build_api_s3_path(_locations(tmp_path), observation_date=None, valuation_type=None)

    assert path.endswith(
        "/executions/data/fact_simulation/observation_date=*/run_mode=simulation/"
        "valuation_type=*/**/*.parquet"
    )


def test_execute_query_uses_shared_duckdb_adapter_for_s3(monkeypatch, tmp_path):
    locations = _locations(tmp_path, storage_root="s3://results-bucket/application")
    s3 = S3ConnectionSettings(
        endpoint_url="http://minio:9000",
        key="access-key",
        secret="secret-key",
        region="us-east-1",
        verify_tls=False,
    )
    connection = MagicMock()
    result = MagicMock()
    result.description = [("sample_index",), ("value_rub",)]
    result.fetchall.return_value = [(0, 1.5)]
    connection.execute.return_value = result
    adapter = MagicMock()
    adapter.connect.return_value = connection
    captured_base_paths = []

    def adapter_factory(base_path):
        captured_base_paths.append(base_path)
        return adapter

    monkeypatch.setattr(
        "domains.reporting.services.sql_query_service.DuckDbStorageAdapter",
        adapter_factory,
    )
    service = FactQueryService(locations=locations, s3_settings=s3)

    columns, rows, _ = service.execute_query(
        "SELECT sample_index, value_rub FROM simulation_data",
        observation_date="20260615",
        limit=10,
        fact_slug="fact_simulation",
        run_mode="simulation",
        valuation_type="eod",
    )

    assert columns == ["sample_index", "value_rub"]
    assert rows == [[0, 1.5]]
    assert len(captured_base_paths) == 1
    assert captured_base_paths[0].full_path == ("results-bucket/application/executions/data")
    assert captured_base_paths[0].backend.connection is s3
    adapter.connect.assert_called_once_with()
    executed_sql = connection.execute.call_args.args[0]
    assert (
        "read_parquet('s3://results-bucket/application/executions/data/fact_simulation/"
        in executed_sql
    )
    assert "INSTALL" not in executed_sql.upper()
    connection.close.assert_called_once_with()
