import datetime as dt

import pandas as pd

from domains.reporting.services.deterministic_comparison_service import (
    DeterministicComparisonService,
)


class _QueryStub:
    def __init__(self) -> None:
        self.contract_calls = []
        self.payment_calls = []

    def query_contracts(self, **kwargs):
        self.contract_calls.append(kwargs)
        return pd.DataFrame({"valuation_date": [dt.date(2026, 1, 1)], "reporting2_value": [125.0]})

    def query_payments(self, **kwargs):
        self.payment_calls.append(kwargs)
        return pd.DataFrame(
            {
                "payment_date": [dt.date(2026, 1, 15), dt.date(2026, 2, 15)],
                "payment_amount_usd": [10.0, 20.0],
                "payment_amount_rub": [900.0, 1800.0],
            }
        )


def _params(period_mode: str, target: str) -> dict:
    return {
        "observation_date": dt.date(2026, 1, 1),
        "period_start": dt.date(2026, 1, 1),
        "period_end": dt.date(2026, 12, 31),
        "period_mode": period_mode,
        "target": target,
        "valuation_type": "eod",
        "gl_accounts": None,
        "markets": None,
        "products": None,
        "dynamic_filters": {"scenario": "default"},
    }


def test_load_values_reads_fact_deterministic_contract_service_as_one_result():
    query = _QueryStub()
    service = DeterministicComparisonService(query)

    value, _ = service.load_values(**_params("valuations", "value_usd"))

    assert value == 125.0
    assert query.contract_calls[0]["run_mode"] == "deterministic"
    assert service.build_statistics(value) == {
        "COUNT": 1,
        "AVG": 125.0,
        "MED": 125.0,
        "MIN": 125.0,
        "MAX": 125.0,
        "STD": None,
        "P05": None,
        "P95": None,
        "CVaR95": None,
    }


def test_build_monthly_uses_deterministic_payments_and_cumulative_path():
    query = _QueryStub()
    service = DeterministicComparisonService(query)
    _, frame = service.load_values(**_params("payments", "value_rub"))

    monthly = service.build_monthly(
        frame=frame,
        period_mode="payments",
        target="value_rub",
        monthly_mode="cumulative_cash_position",
    )

    assert [item["values"] for item in monthly] == [[900.0], [2700.0]]
    assert all(item["sample_count"] == 1 for item in monthly)
