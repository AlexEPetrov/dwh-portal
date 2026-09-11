"""Tests for Balance report-currency conversion boundaries."""

import datetime as dt

import pytest

from domains.risk.services.balance.uom_conversion import BalanceMoneyUnits, BalanceUomConverter


def test_default_scale_round_trips_without_fx() -> None:
    converter = BalanceUomConverter(BalanceMoneyUnits.from_options("rub", "bln_rub"))

    assert converter.display_value(2_000_000_000, dt.date(2026, 1, 1)) == 2.0
    assert converter.storage_value(2.0, dt.date(2026, 1, 1)) == 2_000_000_000


def test_date_aware_usd_conversion_applies_fx_before_scale() -> None:
    seen: list[tuple[str, str, dt.date]] = []

    def fx(value: float, source: str, target: str, date: dt.date) -> float:
        seen.append((source, target, date))
        return value / 100.0 if target == "usd" else value * 100.0

    converter = BalanceUomConverter(
        BalanceMoneyUnits.from_options("usd", "mln_usd"), fx_conversion=fx
    )
    date = dt.date(2026, 5, 8)

    assert (
        converter.convert(
            1_000_000_000,
            BalanceMoneyUnits.from_options("rub", "bln_rub").source,
            converter.units.public,
            date,
        )
        == 10.0
    )
    assert converter.storage_value(10.0, date) == 10_000_000
    assert seen == [("rub", "usd", date)]


def test_report_currency_must_use_the_balance_currency() -> None:
    with pytest.raises(ValueError, match="configured balance currency"):
        BalanceMoneyUnits.from_options("rub", "mln_usd")
