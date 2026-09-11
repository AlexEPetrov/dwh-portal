from __future__ import annotations

import datetime as dt

import pandas as pd

from domains.reporting.services.simulation_query_service import SimulationQueryService


class _AdapterStub:
    def valuation_hive_path_glob(self, *, observation_date, run_mode, valuation_type):
        return "dummy/**/*.parquet"

    def to_duckdb_read_call(self, glob_path, *, file_format, hive_partitioning):
        return "simulation_data"


class _QueryResultStub:
    def __init__(self, columns, rows):
        self.description = [(column,) for column in columns]
        self._rows = rows

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def fetchall(self):
        return self._rows


class _CombinedConnectionStub:
    def __init__(self):
        self.executed_sql = []

    def execute(self, sql):
        self.executed_sql.append(sql)
        if "SELECT * FROM stats" in sql:
            return _QueryResultStub(
                [
                    "count",
                    "avg_val",
                    "median_val",
                    "min_val",
                    "max_val",
                    "std_val",
                    "p05",
                    "p95",
                    "cvar95",
                ],
                [(3, 20.0, 20.0, 10.0, 30.0, 8.0, 11.0, 29.0, 10.0)],
            )
        return _QueryResultStub(["target_value"], [(30.0,), (10.0,), (20.0,)])

    def close(self):
        pass


class _CombinedAdapterStub(_AdapterStub):
    def __init__(self):
        self.connection = _CombinedConnectionStub()

    def connect(self):
        return self.connection


def test_query_monthly_breakdown_groups_values_and_returns_flexible_statistics(monkeypatch):
    service = SimulationQueryService(_AdapterStub())

    def fake_execute(sql: str) -> pd.DataFrame:
        assert "DATE_TRUNC('month'" in sql
        assert "GROUP BY bucket_month, sample_index" in sql
        return pd.DataFrame(
            [
                {"month": dt.date(2026, 1, 1), "sample_index": 0, "target_value": 10.0},
                {"month": dt.date(2026, 1, 1), "sample_index": 1, "target_value": 20.0},
                {"month": dt.date(2026, 2, 1), "sample_index": 0, "target_value": 30.0},
            ]
        )

    monkeypatch.setattr(service, "_execute_query", fake_execute)

    result = service.query_monthly_breakdown(
        run_mode="simulation",
        valuation_type="eod",
        observation_date=dt.date(2026, 1, 1),
        period_start=dt.date(2026, 1, 1),
        period_end=dt.date(2026, 2, 1),
        period_mode="valuations",
        target="value_rub",
    )

    assert [item["month"] for item in result] == ["2026-01-01", "2026-02-01"]
    assert result[0]["values"] == [10.0, 20.0]
    assert [stat.metric for stat in result[0]["statistics"]] == ["P10", "P50", "P90", "AVG"]
    assert result[0]["sample_count"] == 2


def test_query_monthly_breakdown_cumulative_cash_position_sums_per_sample_path(monkeypatch):
    service = SimulationQueryService(_AdapterStub())

    def fake_execute(sql: str) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {"month": dt.date(2026, 1, 1), "sample_index": 0, "target_value": 10.0},
                {"month": dt.date(2026, 1, 1), "sample_index": 1, "target_value": -5.0},
                {"month": dt.date(2026, 2, 1), "sample_index": 0, "target_value": -30.0},
                {"month": dt.date(2026, 2, 1), "sample_index": 1, "target_value": -10.0},
            ]
        )

    monkeypatch.setattr(service, "_execute_query", fake_execute)

    result = service.query_monthly_breakdown(
        run_mode="simulation",
        valuation_type="eod",
        observation_date=dt.date(2026, 1, 1),
        period_start=dt.date(2026, 1, 1),
        period_end=dt.date(2026, 2, 1),
        period_mode="valuations",
        target="value_rub",
        monthly_mode="cumulative_cash_position",
    )

    assert [item["month"] for item in result] == ["2026-01-01", "2026-02-01"]
    assert result[0]["values"] == [10.0, -5.0]
    assert result[1]["values"] == [-20.0, -15.0]


def test_query_monthly_breakdown_keeps_static_only_months(monkeypatch):
    service = SimulationQueryService(_AdapterStub())

    def fake_execute(sql: str) -> pd.DataFrame:
        assert "sample_index = -2" in sql
        return pd.DataFrame(
            [
                {"month": dt.date(2026, 1, 1), "sample_index": -2, "target_value": 12.0},
                {"month": dt.date(2026, 3, 1), "sample_index": -2, "target_value": 30.0},
            ]
        )

    monkeypatch.setattr(service, "_execute_query", fake_execute)
    result = service.query_monthly_breakdown(
        run_mode="simulation",
        valuation_type="eod",
        observation_date=dt.date(2026, 1, 1),
        period_start=dt.date(2026, 1, 1),
        period_end=dt.date(2026, 3, 1),
        period_mode="payments",
        target="value_rub",
    )

    assert [item["month"] for item in result] == ["2026-01-01", "2026-03-01"]
    assert [item["values"] for item in result] == [[12.0], [30.0]]
    assert result.has_simulation is False
    assert result.has_static is False


def test_query_monthly_breakdown_static_only_cumulative_uses_saved_values(monkeypatch):
    service = SimulationQueryService(_AdapterStub())

    def fake_execute(sql: str) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {"month": dt.date(2026, 1, 1), "sample_index": -2, "target_value": 12.0},
                {"month": dt.date(2026, 3, 1), "sample_index": -2, "target_value": 30.0},
            ]
        )

    monkeypatch.setattr(service, "_execute_query", fake_execute)
    result = service.query_monthly_breakdown(
        run_mode="simulation",
        valuation_type="eod",
        observation_date=dt.date(2026, 1, 1),
        period_start=dt.date(2026, 1, 1),
        period_end=dt.date(2026, 3, 1),
        period_mode="payments",
        target="value_rub",
        monthly_mode="cumulative_cash_position",
    )

    assert [item["values"] for item in result] == [[12.0], [42.0]]


def test_query_combined_returns_values_in_sample_index_order():
    adapter = _CombinedAdapterStub()
    service = SimulationQueryService(adapter)

    result = service.query_combined(
        run_mode="simulation",
        valuation_type="eod",
        observation_date=dt.date(2026, 1, 1),
        period_start=dt.date(2026, 1, 1),
        period_end=dt.date(2026, 2, 1),
        period_mode="valuations",
        target="value_rub",
    )

    samples_sql = adapter.connection.executed_sql[1]
    assert "ORDER BY sample_index" in samples_sql
    assert "ORDER BY target_value" not in samples_sql
    assert result["sample_values"] == [30.0, 10.0, 20.0]


def test_sample_query_sql_merges_static_baseline_into_simulation_samples():
    service = SimulationQueryService(_AdapterStub())

    sql = service.build_sample_target_sql(
        run_mode="simulation",
        valuation_type="eod",
        observation_date=dt.date(2026, 1, 1),
        period_start=dt.date(2026, 1, 1),
        period_end=dt.date(2026, 2, 1),
        period_mode="valuations",
        target="value_rub",
    )

    assert "run_mode = 'simulation'" in sql
    assert "run_mode = 'static'" in sql
    assert "COALESCE(s.simulation_value, 0) + COALESCE(st.static_value, 0)" in sql
    assert "sample_index IN (-2, -1)" in sql
    assert "SELECT -2 FROM static" in sql
    static_sql = sql.split("static AS")[1].split("sample_universe AS")[0]
    assert "scenario = 'default'" in static_sql


def test_sample_query_sql_filters_selected_scenario_only_on_simulation_rows():
    service = SimulationQueryService(_AdapterStub())

    sql = service.build_sample_target_sql(
        run_mode="simulation",
        valuation_type="eod",
        observation_date=dt.date(2026, 1, 1),
        period_start=dt.date(2026, 1, 1),
        period_end=dt.date(2026, 2, 1),
        period_mode="valuations",
        target="value_rub",
        dynamic_filters={"scenario": "base"},
    )

    simulation_sql = sql.split("simulation AS")[1].split("static AS")[0]
    static_sql = sql.split("static AS")[1].split("sample_universe AS")[0]
    assert "scenario = 'base'" in simulation_sql
    assert "scenario = 'base'" not in static_sql
    assert "scenario = 'default'" in static_sql


def test_query_statistics_aliases_per_sample_aggregation_as_target_value(monkeypatch):
    service = SimulationQueryService(_AdapterStub())
    captured_sql = ""

    def fake_execute(sql: str) -> pd.DataFrame:
        nonlocal captured_sql
        captured_sql = sql
        return pd.DataFrame(
            [
                {
                    "count": 1,
                    "avg": 10.0,
                    "med": 10.0,
                    "min": 10.0,
                    "max": 10.0,
                    "std": 0.0,
                    "p05": 10.0,
                    "p95": 10.0,
                    "cvar95": 10.0,
                }
            ]
        )

    monkeypatch.setattr(service, "_execute_query", fake_execute)

    service.query_statistics(
        run_mode="simulation",
        valuation_type="eod",
        observation_date=dt.date(2026, 1, 1),
        period_start=dt.date(2026, 1, 1),
        period_end=dt.date(2026, 2, 1),
        period_mode="valuations",
        target="value_rub",
    )

    assert "SUM(value_rub) AS target_value" in captured_sql
    assert "WHERE target_value IS NOT NULL" in captured_sql


def test_query_samples_aggregated_requests_sample_index_order(monkeypatch):
    service = SimulationQueryService(_AdapterStub())
    captured = {}

    def fake_query_sample_target_dataframe(**kwargs):
        captured.update(kwargs)
        return pd.DataFrame({"sample_index": [0, 1, 2], "target_value": [30.0, 10.0, 20.0]})

    monkeypatch.setattr(
        service,
        "query_sample_target_dataframe",
        fake_query_sample_target_dataframe,
    )

    result = service.query_samples_aggregated(
        run_mode="simulation",
        valuation_type="eod",
        observation_date=dt.date(2026, 1, 1),
        period_start=dt.date(2026, 1, 1),
        period_end=dt.date(2026, 2, 1),
        period_mode="valuations",
        target="value_rub",
    )

    assert captured["order_by"] == "sample_index"
    assert result["sample_values"] == [30.0, 10.0, 20.0]


def test_monthly_source_metadata_is_not_inferred_from_hybrid_sample_marker(monkeypatch):
    service = SimulationQueryService(_AdapterStub())

    def fake_execute(sql: str) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {
                    "month": dt.date(2026, 1, 1),
                    "sample_index": 0,
                    "target_value": 15.0,
                    "has_simulation": True,
                    "has_static": True,
                }
            ]
        )

    monkeypatch.setattr(service, "_execute_query", fake_execute)
    result = service.query_monthly_breakdown(
        run_mode="simulation",
        valuation_type="eod",
        observation_date=dt.date(2026, 1, 1),
        period_start=dt.date(2026, 1, 1),
        period_end=dt.date(2026, 1, 1),
        period_mode="valuations",
        target="value_rub",
    )

    assert result.has_simulation is True
    assert result.has_static is True
    assert "has_simulation" not in result[0]
