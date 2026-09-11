import datetime as dt

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.valuation import results as results_api
from domains.reporting.services.simulation_data_service import SimulationDataService


class _LazyQueryServiceStub:
    values = [float(value) for value in range(20_000)]

    def __init__(self) -> None:
        self.statistics_calls = 0
        self.combined_calls: list[bool] = []

    def query_statistics(self, **_kwargs):
        self.statistics_calls += 1
        return self._statistics()

    def query_combined(self, *, include_density, **_kwargs):
        self.combined_calls.append(include_density)
        density = SimulationDataService().build_distribution(self.values, bins=60)
        return {
            "statistics": self._statistics(),
            "sample_values": self.values,
            "sample_count": len(self.values),
            "x_grid": list(density.x_grid) if include_density else [],
            "density": list(density.density) if include_density else [],
            "median": density.median if include_density else 9_999.5,
            "duckdb_sql": ["SELECT target_value FROM per_sample"],
        }

    @classmethod
    def _statistics(cls):
        return {
            "COUNT": len(cls.values),
            "AVG": 9_999.5,
            "MED": 9_999.5,
            "MIN": 0.0,
            "MAX": 19_999.0,
            "STD": 5_773.5,
            "P05": 999.95,
            "P95": 18_999.05,
            "CVaR95": 499.5,
        }


def _client(monkeypatch) -> tuple[TestClient, _LazyQueryServiceStub]:
    query_service = _LazyQueryServiceStub()

    def fake_cqrs_query(query):
        request = query.request
        payload = query_service.query_combined(
            include_density=False,
            run_mode=request.run_mode.value,
            valuation_type=request.valuation_type,
            observation_date=request.observation_date,
            period_start=request.period.start,
            period_end=request.period.end,
            period_mode=request.period_mode.value,
            target=request.target.value,
        )
        from domains.reporting.models.simulation_analysis import (
            QueryDiagnostics,
            SampleSetResult,
            SampleValue,
            SourceMetadata,
        )

        return SampleSetResult(
            tuple(
                SampleValue(index, value) for index, value in enumerate(payload["sample_values"])
            ),
            QueryDiagnostics(
                payload["duckdb_sql"][0], SourceMetadata(True, False), payload["sample_count"]
            ),
        )

    monkeypatch.setattr(results_api, "_query_simulation_analysis", fake_cqrs_query)
    app = FastAPI()
    app.include_router(results_api.results_router, prefix="/valuation")
    return TestClient(app), query_service


def _params(payload_mode: str) -> dict[str, str]:
    return {
        "period_start": "2026-01-01",
        "period_end": "2026-12-31",
        "observation_date": dt.date(2026, 1, 15).isoformat(),
        "payload_mode": payload_mode,
    }


def test_combined_payload_modes_do_not_duplicate_heavy_arrays(monkeypatch):
    client, query_service = _client(monkeypatch)

    statistics_response = client.get(
        "/valuation/results/simulation/combined", params=_params("statistics")
    )
    distribution_response = client.get(
        "/valuation/results/simulation/combined", params=_params("distribution")
    )
    raw_response = client.get("/valuation/results/simulation/combined", params=_params("raw"))

    assert statistics_response.status_code == 200
    assert distribution_response.status_code == 200
    assert raw_response.status_code == 200
    statistics = statistics_response.json()
    distribution = distribution_response.json()
    raw = raw_response.json()

    assert "values" not in statistics and "figure" not in statistics
    assert "values" not in distribution and "figure" in distribution
    assert "values" in raw and "figure" not in raw
    assert len(raw["values"]) == len(query_service.values)
    assert query_service.statistics_calls == 0
    assert query_service.combined_calls == [False, False, False]


def test_distribution_payload_stays_bounded_and_smaller_than_raw(monkeypatch):
    client, _query_service = _client(monkeypatch)

    distribution_response = client.get(
        "/valuation/results/simulation/combined",
        params={**_params("distribution"), "chart_type": "box"},
    )
    raw_response = client.get("/valuation/results/simulation/combined", params=_params("raw"))

    forecast_values = distribution_response.json()["figure"]["data"][0]["y"]
    assert (
        len(forecast_values)
        == results_api.SimulationPlotlyFigureSpecBuilder.MAX_DISTRIBUTION_SAMPLE_POINTS
    )
    assert len(distribution_response.content) < len(raw_response.content) / 2


class _DeterministicReaderStub:
    def load_values(self, **_kwargs):
        return 125.0, None

    @staticmethod
    def build_statistics(value):
        return {
            "COUNT": 1,
            "AVG": value,
            "MED": value,
            "MIN": value,
            "MAX": value,
            "STD": None,
            "P05": None,
            "P95": None,
            "CVaR95": None,
        }


def test_combined_deterministic_mode_uses_one_sample_compatibility_reader(monkeypatch):
    monkeypatch.setattr(
        results_api, "_create_deterministic_results_reader", lambda: _DeterministicReaderStub()
    )
    app = FastAPI()
    app.include_router(results_api.results_router, prefix="/valuation")
    client = TestClient(app)

    response = client.get(
        "/valuation/results/simulation/combined",
        params={**_params("raw"), "run_mode": "deterministic", "target": "value_usd"},
    )

    assert response.status_code == 200
    assert response.json()["sample_count"] == 1
    assert response.json()["values"] == [125.0]


def test_combined_deterministic_mode_rejects_prices():
    app = FastAPI()
    app.include_router(results_api.results_router, prefix="/valuation")
    client = TestClient(app)

    response = client.get(
        "/valuation/results/simulation/combined",
        params={"run_mode": "deterministic", **_params("statistics"), "period_mode": "prices"},
    )

    assert response.status_code == 400
    assert "does not support prices mode" in response.json()["detail"]
