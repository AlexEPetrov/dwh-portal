import datetime as dt

import pandas as pd

from domains.reporting.services import observation_comparison_service as module
from domains.reporting.services.observation_comparison_service import ObservationComparisonService


def test_load_single_factor_average_uses_named_value_column(monkeypatch):
    monkeypatch.setattr(
        module,
        "load_quote_as_dataframe",
        lambda **_kwargs: pd.DataFrame(
            {"sample_index": [0, 1, 2], "brent_avg": [10.0, 20.0, None]}
        ),
    )

    result = ObservationComparisonService._load_single_factor_average(
        factor_name="brent",
        observation_date=dt.date(2026, 6, 15),
        period_start=dt.date(2026, 1, 1),
        period_end=dt.date(2026, 12, 31),
    )

    assert result == 15.0


def test_load_quote_averages_returns_missing_factor_values_as_none(monkeypatch):
    class _MetadataService:
        def load(self, **_kwargs):
            return None

    monkeypatch.setattr(module, "SimulationRunMetadataService", _MetadataService)
    monkeypatch.setattr(
        ObservationComparisonService,
        "_load_single_factor_average",
        staticmethod(lambda **_kwargs: None),
    )

    result = ObservationComparisonService._load_quote_averages(
        observation_date=dt.date(2026, 6, 15),
        period_start=dt.date(2026, 1, 1),
        period_end=dt.date(2026, 12, 31),
        valuation_type="eod",
    )

    assert result == module.QuoteAveragePoint(
        observation_date=dt.date(2026, 6, 15),
        brent=None,
        ttf=None,
        usdrub=None,
    )
