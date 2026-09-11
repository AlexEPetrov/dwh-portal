import datetime as dt
from unittest.mock import MagicMock

from domains.risk.queries.index import GetIndexValuesHandler


def test_index_query_builds_python_context_with_default_valuation_type(monkeypatch):
    """The Python index query supplies the required default valuation type."""
    data_context = MagicMock()
    data_context.indexes.get_first.return_value = MagicMock()
    calculator_result = MagicMock(value=12.5)
    calculator = MagicMock()
    calculator.execute.return_value = calculator_result

    data_context_manager = MagicMock()
    data_context_manager.__enter__.return_value = data_context
    data_context_manager.__exit__.return_value = None

    monkeypatch.setattr(
        "domains.risk.queries.index.ValuationRunDataContext",
        lambda: data_context_manager,
    )
    monkeypatch.setattr(
        "domains.risk.queries.index.IndexRefCalculator",
        lambda: calculator,
    )

    values = GetIndexValuesHandler().execute(
        observation_date=dt.date(2026, 6, 1),
        slug="test-index",
        min_date=dt.date(2026, 6, 1),
        max_date=dt.date(2026, 6, 1),
    )

    assert values[0]["value"] == 12.5
    assert calculator.execute.call_args.args[1].params.valuation_type == "eod"
