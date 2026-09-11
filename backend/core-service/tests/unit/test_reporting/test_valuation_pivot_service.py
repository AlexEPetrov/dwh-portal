import pandas as pd

from domains.reporting.services.valuation_pivot_service import ValuationPivotService


def test_monthly_waprice_is_monthly_value_divided_by_monthly_volume() -> None:
    df = pd.DataFrame(
        [
            {
                "contract_name": "C1",
                "counterparty": "CP",
                "gl_account": "OP_REV_SALES",
                "delivery_market": "DM",
                "product": "GAS",
                "supply_path": "SP",
                "valuation_date": pd.Timestamp("2026-01-01").date(),
                "valuation_month": 1,
                "valuation_year": 2026,
                "reporting2_value": 100.0,
                "reporting2_volume": 10.0,
                "reporting2_waprice": 10.0,
                "reporting1_value": 100.0,
                "reporting1_volume": 10.0,
                "reporting1_waprice": 10.0,
                "value": 100.0,
                "volume": 10.0,
                "waprice": 10.0,
                "currency": "usd",
                "volume_uom": "1000m3",
                "pricing_uom": "usd/1000m3",
            },
            {
                "contract_name": "C1",
                "counterparty": "CP",
                "gl_account": "OP_REV_SALES",
                "delivery_market": "DM",
                "product": "GAS",
                "supply_path": "SP",
                "valuation_date": pd.Timestamp("2026-01-02").date(),
                "valuation_month": 1,
                "valuation_year": 2026,
                "reporting2_value": 400.0,
                "reporting2_volume": 20.0,
                "reporting2_waprice": 20.0,
                "reporting1_value": 400.0,
                "reporting1_volume": 20.0,
                "reporting1_waprice": 20.0,
                "value": 400.0,
                "volume": 20.0,
                "waprice": 20.0,
                "currency": "usd",
                "volume_uom": "1000m3",
                "pricing_uom": "usd/1000m3",
            },
        ]
    )

    result = ValuationPivotService().build_pivot(df, currency="usd", interval="monthly")

    waprice_row = next(row for row in result.data if row["property_name"] == "waprice")
    assert waprice_row["2026-01"] == 500.0 / 30.0


def test_monthly_waprice_is_null_when_monthly_volume_is_zero() -> None:
    df = pd.DataFrame(
        [
            {
                "contract_name": "C1",
                "counterparty": "CP",
                "gl_account": "OP_REV_SALES",
                "delivery_market": "DM",
                "product": "GAS",
                "supply_path": "SP",
                "valuation_date": pd.Timestamp("2026-01-01").date(),
                "valuation_month": 1,
                "valuation_year": 2026,
                "reporting2_value": 100.0,
                "reporting2_volume": 0.0,
                "reporting2_waprice": 0.0,
                "reporting1_value": 100.0,
                "reporting1_volume": 0.0,
                "reporting1_waprice": 0.0,
                "value": 100.0,
                "volume": 0.0,
                "waprice": 0.0,
                "currency": "usd",
                "volume_uom": "1000m3",
                "pricing_uom": "usd/1000m3",
            }
        ]
    )

    result = ValuationPivotService().build_pivot(df, currency="usd", interval="monthly")

    waprice_row = next(row for row in result.data if row["property_name"] == "waprice")
    assert waprice_row["2026-01"] is None
