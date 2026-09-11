"""Unit tests for the isolated ad-hoc valuation transport adapter."""

import datetime as dt
from unittest.mock import Mock
from uuid import UUID

import grpc
import pytest

import proto.curve_data_service_pb2 as pb2
from domains.risk.services.valuation.remote.ad_hoc import (
    AdHocValuationClient,
    build_usdrub_year_avg_request,
    prepare_save_fx_snapshot,
    save_fx_operation_id,
    validate_ad_hoc_response,
)


def test_builds_save_fx_request_for_cbr_year_average() -> None:
    request = build_usdrub_year_avg_request(
        request_id="run-1",
        operation_id="fx-1",
        observation_date=dt.date(2026, 2, 1),
        balance_year=2026,
    )

    assert "USDRUB_CBR_Y_AVG" in request.definition_json


def test_builds_yearly_usdrub_request_without_python_calculation() -> None:
    request = build_usdrub_year_avg_request(
        request_id="run-1",
        operation_id="fx-1",
        observation_date=dt.date(2026, 2, 1),
        balance_year=2026,
        samples_from=4,
        samples_count=2,
    )

    assert request.operation_kind == "index"
    assert request.samples_from == 4
    assert request.samples_count == 2
    assert request.valuation_start_date == dt.date(2026, 1, 1).toordinal()
    assert request.valuation_end_date == dt.date(2026, 12, 31).toordinal()


def test_builds_yearly_usdrub_request_from_uuid_identifiers() -> None:
    request = build_usdrub_year_avg_request(
        request_id=UUID("018f2b34-1234-7abc-8def-123456789abc"),
        operation_id=UUID("018f2b34-1234-7abc-8def-123456789abd"),
        observation_date=dt.date(2026, 2, 1),
        balance_year=2026,
    )

    assert request.request_id == "018f2b34-1234-7abc-8def-123456789abc"
    assert request.operation_id == "018f2b34-1234-7abc-8def-123456789abd"


def test_ad_hoc_rpc_failure_is_mapped_to_clear_python_error() -> None:
    client = object.__new__(AdHocValuationClient)
    client._stub = Mock()

    rpc_error = grpc.RpcError()
    rpc_error.details = lambda: "simulation lifecycle is not initialized"
    client._stub.CalculateAdHoc.side_effect = rpc_error
    request = build_usdrub_year_avg_request(
        request_id="run-1",
        operation_id="fx-1",
        observation_date=dt.date(2026, 2, 1),
        balance_year=2026,
    )

    with pytest.raises(
        ValueError, match="Calc-service could not calculate Balance FX.*simulation lifecycle"
    ):
        client.calculate_usdrub_year_avg(request)


def test_save_fx_snapshot_is_prepared_once_for_repeated_requests(monkeypatch) -> None:
    from domains.risk.services.valuation.remote import ad_hoc

    ad_hoc._PREPARED_SIMULATION_SNAPSHOTS.clear()
    calls = []

    class Command:
        request_id = UUID("018f2b34-1234-7abc-8def-123456789abc")
        target_sample_count = 2
        observation_date = dt.date(2026, 6, 1)
        valuation_type = "eod"

    monkeypatch.setattr(
        ad_hoc,
        "_prepare_save_fx_snapshot_impl",
        lambda command: calls.append(command) or str(command.request_id),
        raising=False,
    )

    first = prepare_save_fx_snapshot(command=Command())
    second = prepare_save_fx_snapshot(command=Command())

    assert first == second == str(Command.request_id)
    assert len(calls) == 1


def test_save_fx_snapshot_operation_id_uses_observation_date_and_valuation_type(
    monkeypatch,
) -> None:
    from domains.risk.services.valuation.remote import ad_hoc

    captured = []

    class Command:
        request_id = UUID("018f2b34-1234-7abc-8def-123456789abe")
        target_sample_count = 2
        observation_date = dt.date(2026, 6, 1)
        valuation_type = "eod"

    monkeypatch.setattr(
        ad_hoc,
        "_prepare_save_fx_snapshot_impl",
        lambda command: captured.append(command) or str(command.request_id),
    )
    ad_hoc._PREPARED_SIMULATION_SNAPSHOTS.clear()
    prepare_save_fx_snapshot(command=Command())

    assert (
        save_fx_operation_id(captured[0].observation_date, captured[0].valuation_type)
        == "20260601/eod"
    )


def test_save_fx_snapshot_reuse_is_scoped_to_request_id(monkeypatch) -> None:
    from domains.risk.services.valuation.remote import ad_hoc

    ad_hoc._PREPARED_SIMULATION_SNAPSHOTS.clear()
    calls = []

    class Command:
        request_id = "fx-request-1"
        target_sample_count = 2
        observation_date = dt.date(2026, 6, 1)
        valuation_type = "eod"

    monkeypatch.setattr(
        ad_hoc,
        "_prepare_save_fx_snapshot_impl",
        lambda command: calls.append(command.request_id) or command.request_id,
    )

    prepare_save_fx_snapshot(command=Command())

    class OtherCommand(Command):
        request_id = "fx-request-2"

    prepare_save_fx_snapshot(command=OtherCommand())

    assert calls == ["fx-request-1", "fx-request-2"]


def test_save_fx_streaming_uses_fx_only_single_reader(monkeypatch) -> None:
    monkeypatch.setenv("APP_CALC_SERVICE_HOST", "http://calc-service")
    monkeypatch.setenv("APP_CALC_SERVICE_GRPC_SOCK", "unix:///tmp/calc.sock")
    monkeypatch.setenv("APP_CALC_SERVICE_API_KEY", "test-key")
    from domains.risk.services.valuation.remote import monte_carlo

    captured = {}

    class Streamer:
        def __init__(self, config, servers):
            captured["curves"] = [curve.get_slug_or_name() for curve in config.curves]

        def stream_immediate_chunks(self, params, **kwargs):
            captured["kwargs"] = kwargs

    class Registry:
        def simulation_source_path(self, params):
            return "simulation-path"

    class Curves:
        _simulation_files = {"CBR_USD_RUB": object(), "OTHER": object()}

    class Definitions:
        def get_all(self):
            return [
                type("Curve", (), {"get_slug_or_name": lambda self: "CBR_USD_RUB"})(),
                type("Curve", (), {"get_slug_or_name": lambda self: "OTHER"})(),
            ]

    class Data:
        curves = Curves()
        curve_definitions = Definitions()

    monkeypatch.setattr(monte_carlo, "get_file_store_registry", lambda: Registry())
    monkeypatch.setattr(monte_carlo, "SimulationChunkStreamer", Streamer)
    monkeypatch.setattr(monte_carlo, "SOCK_FILE", "test-sock")

    params = type("Params", (), {"request_id": "balance-request", "samples_count": 2})()
    monte_carlo.SimulationGrpcRunner.send_simulations_to_grpc2(
        params, Data(), required_curve_names={"CBR_USD_RUB"}
    )

    assert captured["curves"] == ["CBR_USD_RUB"]
    assert captured["kwargs"] == {"single_reader": True}


def test_response_requires_exact_sample_coverage_and_finite_nonzero_values() -> None:
    response = pb2.AdHocCalculationResponse(
        operation_id="fx-1",
        unit="rub/usd",
        status="SUCCESS",
        entries=[
            pb2.AdHocCalculationEntry(sample_index=4, value=100.0),
            pb2.AdHocCalculationEntry(sample_index=5, value=101.0),
        ],
    )

    result = validate_ad_hoc_response(response, expected_indices=[4, 5])

    assert [item.sample_index for item in result.values] == [4, 5]


@pytest.mark.parametrize(
    "entries",
    [
        [pb2.AdHocCalculationEntry(sample_index=4, value=100.0)],
        [
            pb2.AdHocCalculationEntry(sample_index=4, value=100.0),
            pb2.AdHocCalculationEntry(sample_index=4, value=101.0),
        ],
        [
            pb2.AdHocCalculationEntry(sample_index=4, value=0.0),
            pb2.AdHocCalculationEntry(sample_index=5, value=101.0),
        ],
    ],
)
def test_response_rejects_incomplete_duplicate_or_zero_values(entries) -> None:
    response = pb2.AdHocCalculationResponse(status="SUCCESS", entries=entries)

    with pytest.raises(ValueError):
        validate_ad_hoc_response(response, expected_indices=[4, 5])
