import datetime

from domains.risk.queries.models import CurvePointsQuery


def _query(**overrides) -> CurvePointsQuery:
    values = {
        "observation_date": datetime.date(2026, 8, 15),
        "curve": "TEST_FWD",
        "min_date": datetime.date(2026, 8, 1),
        "max_date": datetime.date(2026, 8, 31),
        "scenario": "default",
    }
    values.update(overrides)
    return CurvePointsQuery(**values)


def test_curve_points_query_allows_forecast_by_default() -> None:
    assert _query().allow_forecast is True


def test_curve_points_query_preserves_disabled_forecast_selection() -> None:
    assert _query(allow_forecast=False).allow_forecast is False
