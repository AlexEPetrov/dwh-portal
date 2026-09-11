import datetime as dt
import uuid

from domains.risk.models.common import ValuationRun
from domains.risk.services.valuation import valuation_run_state_service


class _FakeValuationRunObjects:
    runs: dict[uuid.UUID, ValuationRun] = {}

    def __init__(self, *_args, **_kwargs):
        pass

    def update(self, run: ValuationRun):
        self.runs[run.id] = run
        return run, None

    def get_by_id(self, request_id: uuid.UUID):
        return self.runs.get(request_id)

    def get_all(self):
        return list(self.runs.values())


class _FakeSessionContext:
    session = None

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


def test_created_run_becomes_running_when_background_command_starts(monkeypatch):
    monkeypatch.setattr(
        valuation_run_state_service,
        "ValuationRunObjects",
        _FakeValuationRunObjects,
    )
    request_id = uuid.uuid4()
    _FakeValuationRunObjects.runs = {
        request_id: ValuationRun(
            id=request_id,
            run_mode="simulation",
            status="created",
            start_time=dt.datetime(2026, 7, 20, 10, 0, 0),
        )
    }

    run = valuation_run_state_service.ValuationRunLoggingService.mark_valuation_run_running(
        request_id
    )

    assert run is not None
    assert _FakeValuationRunObjects.runs[request_id].status == "running"
    assert _FakeValuationRunObjects.runs[request_id].finish_time is None


def test_failed_background_chain_marks_non_terminal_run_failed(monkeypatch):
    monkeypatch.setattr(
        valuation_run_state_service,
        "ValuationRunObjects",
        _FakeValuationRunObjects,
    )
    request_id = uuid.uuid4()
    _FakeValuationRunObjects.runs = {
        request_id: ValuationRun(
            id=request_id,
            run_mode="simulation",
            status="running",
            start_time=dt.datetime(2026, 7, 20, 10, 0, 0),
        )
    }

    run = valuation_run_state_service.ValuationRunLoggingService.fail_valuation_run_by_request_id(
        request_id, "calc-service failed"
    )

    assert run is not None
    assert _FakeValuationRunObjects.runs[request_id].status == "failed"
    assert _FakeValuationRunObjects.runs[request_id].message == "calc-service failed"
    assert _FakeValuationRunObjects.runs[request_id].finish_time is not None


def test_late_running_update_does_not_override_completed_status(monkeypatch):
    monkeypatch.setattr(
        valuation_run_state_service,
        "ValuationRunObjects",
        _FakeValuationRunObjects,
    )
    request_id = uuid.uuid4()
    _FakeValuationRunObjects.runs = {
        request_id: ValuationRun(
            id=request_id,
            run_mode="simulation",
            status="completed",
            start_time=dt.datetime(2026, 7, 20, 10, 0, 0),
            finish_time=dt.datetime(2026, 7, 20, 10, 5, 0),
        )
    }

    run = valuation_run_state_service.ValuationRunLoggingService.mark_valuation_run_running(
        request_id
    )

    assert run is None
    assert _FakeValuationRunObjects.runs[request_id].status == "completed"


def test_full_background_chain_completion_marks_running_run_completed(monkeypatch):
    monkeypatch.setattr(
        valuation_run_state_service,
        "ValuationRunObjects",
        _FakeValuationRunObjects,
    )
    request_id = uuid.uuid4()
    _FakeValuationRunObjects.runs = {
        request_id: ValuationRun(
            id=request_id,
            run_mode="simulation",
            status="running",
            start_time=dt.datetime(2026, 7, 20, 10, 0, 0),
        )
    }

    run = (
        valuation_run_state_service.ValuationRunLoggingService.complete_valuation_run_by_request_id(
            request_id, "Command chain completed"
        )
    )

    assert run is not None
    assert _FakeValuationRunObjects.runs[request_id].status == "completed"
    assert _FakeValuationRunObjects.runs[request_id].message == "Command chain completed"
    assert _FakeValuationRunObjects.runs[request_id].finish_time is not None


def test_non_terminal_runs_are_marked_interrupted_after_service_restart(monkeypatch):
    monkeypatch.setattr(
        valuation_run_state_service,
        "ValuationRunObjects",
        _FakeValuationRunObjects,
    )
    monkeypatch.setattr(
        valuation_run_state_service,
        "SessionContext",
        _FakeSessionContext,
    )
    created_id = uuid.uuid4()
    running_id = uuid.uuid4()
    completed_id = uuid.uuid4()
    _FakeValuationRunObjects.runs = {
        created_id: ValuationRun(id=created_id, run_mode="deterministic", status="created"),
        running_id: ValuationRun(id=running_id, run_mode="simulation", status="running"),
        completed_id: ValuationRun(id=completed_id, run_mode="simulation", status="completed"),
    }

    updated = (
        valuation_run_state_service.ValuationRunLoggingService.mark_non_terminal_runs_interrupted()
    )

    assert updated == 2
    assert _FakeValuationRunObjects.runs[created_id].status == "interrupted"
    assert _FakeValuationRunObjects.runs[running_id].status == "interrupted"
    assert _FakeValuationRunObjects.runs[completed_id].status == "completed"
    assert _FakeValuationRunObjects.runs[created_id].finish_time is not None
    assert _FakeValuationRunObjects.runs[running_id].message == (
        "Выполнение расчёта прервано после перезапуска сервиса"
    )
