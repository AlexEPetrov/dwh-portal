import datetime as dt

from api.reporting import liquidity as liquidity_api
from domains.reporting.models.simulation_analysis import (
    MonthlyPathResult,
    MonthlyPathValue,
    QueryDiagnostics,
    SourceMetadata,
)
from domains.risk.services.liquidity.service import LiquidityRiskService


def test_liquidity_starts_each_path_at_opening_position() -> None:
    report = LiquidityRiskService().calculate(
        [
            {"month": "2026-01-01", "values": [-30.0, -5.0]},
            {"month": "2026-02-01", "values": [10.0, 20.0]},
        ],
        observation_date=dt.date(2026, 1, 1),
        period_start=dt.date(2026, 1, 1),
        period_end=dt.date(2026, 2, 1),
        currency="rub",
        target="value_rub",
        opening_values=[35.0, 10.0],
        opening_year=2026,
    )

    # Path 0: 35 - 30 + 10 = 15; path 1: 10 - 5 + 20 = 25.
    assert report.peak_funding_need_p95 == 0.0
    assert report.probability_of_cash_deficit == 0.0
    assert report.metadata["opening_year"] == 2026
    assert report.metadata["opening_position_included"] is True


def test_liquidity_marks_missing_opening_position() -> None:
    report = LiquidityRiskService().calculate(
        [{"month": "2026-01-01", "values": [-10.0]}],
        observation_date=dt.date(2026, 1, 1),
        period_start=dt.date(2026, 1, 1),
        period_end=dt.date(2026, 1, 1),
        currency="rub",
        target="value_rub",
        opening_year=2026,
    )

    assert report.peak_funding_need_p95 == 10.0
    assert report.metadata["opening_position_included"] is False


def test_liquidity_has_no_recommendation_without_deficit() -> None:
    report = LiquidityRiskService().calculate(
        [{"month": "2026-01-01", "values": [10.0, 20.0]}],
        observation_date=dt.date(2026, 1, 1),
        period_start=dt.date(2026, 1, 1),
        period_end=dt.date(2026, 1, 1),
        currency="rub",
        target="value_rub",
    )

    assert report.probability_of_cash_deficit == 0.0
    assert report.insights[0]["recommended_actions"] == []


def test_liquidity_endpoint_uses_canonical_full_position_query(monkeypatch) -> None:
    captured = []
    result = MonthlyPathResult(
        paths=(
            MonthlyPathValue(dt.date(2026, 1, 1), 0, 100.0),
            MonthlyPathValue(dt.date(2026, 2, 1), 0, -25.0),
        ),
        diagnostics=QueryDiagnostics(
            sql="SELECT canonical_full_position",
            source=SourceMetadata(has_simulation=True, has_static=False),
            row_count=2,
        ),
    )

    class FakeBus:
        def query(self, query):
            captured.append(query)
            return result

    monkeypatch.setattr(liquidity_api, "CommandBus", lambda: FakeBus())
    monkeypatch.setattr(
        liquidity_api.CommandBus,
        "registered_query_handlers",
        {liquidity_api.LiquiditySimulationAnalysisQuery: object()},
        raising=False,
    )

    response = liquidity_api.get_liquidity_report(
        period_start=dt.date(2026, 1, 1),
        period_end=dt.date(2026, 2, 1),
        observation_date=dt.date(2026, 1, 15),
        source_mode="filter",
    )

    assert response.metadata["opening_position_included"] is False
    assert len(captured) == 1
    assert isinstance(captured[0], liquidity_api.LiquiditySimulationAnalysisQuery)
    assert captured[0].request.source_mode.value == "filter"


def test_liquidity_has_no_recommendation_without_deficit() -> None:
    report = LiquidityRiskService().calculate(
        [{"month": "2026-01-01", "values": [10.0, 20.0]}],
        observation_date=dt.date(2026, 1, 1),
        period_start=dt.date(2026, 1, 1),
        period_end=dt.date(2026, 1, 1),
        currency="rub",
        target="value_rub",
    )

    assert report.probability_of_cash_deficit == 0.0
    assert report.insights[0]["recommended_actions"] == []
