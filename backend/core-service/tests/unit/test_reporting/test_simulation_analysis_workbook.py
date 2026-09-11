import datetime as dt
from types import SimpleNamespace

import openpyxl
import plotly.graph_objects as go
import pytest

from domains.reporting.services.simulation_analysis_workbook import (
    SimulationAnalysisWorkbookRequest,
    SimulationAnalysisWorkbookService,
    SimulationWorkbookSizeError,
)
from domains.reporting.services.simulation_plotly_figure import SimulationPlotlyFigureSpecBuilder
from settings.reporting import ReportingSettings


class _QueryServiceStub:
    def __call__(self, query):
        from domains.reporting.models.simulation_analysis import (
            MonthlyPathResult,
            MonthlyPathValue,
            PhysicalRowsResult,
            PhysicalSimulationRow,
            QueryDiagnostics,
            SampleSetResult,
            SampleValue,
            SourceMetadata,
        )

        diagnostics = QueryDiagnostics("SELECT canonical", SourceMetadata(True, False), 1)
        if query.__class__.__name__ == "CombinedSimulationAnalysisQuery":
            return SampleSetResult(
                (SampleValue(0, 10.0), SampleValue(1, 20.0), SampleValue(2, 30.0)),
                diagnostics,
            )
        if query.__class__.__name__ in {
            "MonthlySimulationAnalysisQuery",
            "PositionSimulationAnalysisQuery",
        }:
            values = [10.0, 20.0, 30.0]
            if query.__class__.__name__ == "PositionSimulationAnalysisQuery":
                values = [20.0, 40.0, 60.0]
            return MonthlyPathResult(
                tuple(
                    MonthlyPathValue(dt.date(2026, 1, 1), index, value)
                    for index, value in enumerate(values)
                ),
                diagnostics,
            )
        return PhysicalRowsResult(
            rows=(
                PhysicalSimulationRow(
                    observation_date=dt.date(2026, 1, 15),
                    run_mode="simulation",
                    valuation_type="eod",
                    valuation_year=2026,
                    valuation_month=1,
                    gl_account="CASH",
                    market=None,
                    product=None,
                    scenario="base",
                    sample_index=0,
                    supply_path=None,
                    legal_entity=None,
                    payment_year=2026,
                    payment_month=1,
                    value_usd=None,
                    value_rub=10.0,
                    volume=None,
                ),
            ),
            columns=("sample_index", "valuation_year", "valuation_month"),
            diagnostics=diagnostics,
        )

    def query_combined(self, **_kwargs):
        return {
            "sample_values": [10.0, 20.0, 30.0],
            "statistics": {"COUNT": 3, "AVG": 20.0, "MED": 20.0},
            "x_grid": [10.0, 20.0, 30.0],
            "density": [0.01, 0.02, 0.01],
            "median": 20.0,
        }

    def query_monthly_breakdown(self, *, monthly_mode, **_kwargs):
        values = [10.0, 20.0, 30.0]
        if monthly_mode == "cumulative_cash_position":
            values = [20.0, 40.0, 60.0]
        return [{"month": "2026-01-01", "values": values}]

    def build_raw_rows_sql(self, **_kwargs):
        return "SELECT 1 AS sample_index, 2026 AS valuation_year, 1 AS valuation_month"

    def connect(self):
        import duckdb

        return duckdb.connect()


def _request() -> SimulationAnalysisWorkbookRequest:
    return SimulationAnalysisWorkbookRequest(
        observation_date=dt.date(2026, 1, 15),
        period_start=dt.date(2026, 1, 1),
        period_end=dt.date(2026, 12, 31),
        dynamic_filters={"scenario": "base"},
    )


def test_export_builds_all_workbook_views_and_embeds_chart_images():
    service = SimulationAnalysisWorkbookService(_QueryServiceStub())

    exported = service.export(_request())
    try:
        workbook = openpyxl.load_workbook(exported.path)
        assert workbook.sheetnames == [
            "Filter",
            "Статистика",
            "Распределение",
            "Помесячно",
            "Liquidity at risk",
            "Raw data 1",
        ]
        assert len(workbook["Распределение"]._images) == 1
        assert len(workbook["Помесячно"]._images) == 1
        assert len(workbook["Liquidity at risk"]._images) == 1
        assert workbook["Raw data 1"]["B1"].value == "valuation_year"
        assert workbook["Raw data 1"]["B2"].value == 2026
        assert workbook["Filter"]["B2"].value == "filter"
        assert exported.filename.endswith("filter_scenario-base.xlsx")
    finally:
        exported.path.unlink(missing_ok=True)


def test_raw_row_limit_fails_before_workbook_is_returned():
    service = SimulationAnalysisWorkbookService(
        _QueryServiceStub(),
        settings=ReportingSettings(simulation_xlsx_max_raw_rows=1),
    )

    with pytest.raises(SimulationWorkbookSizeError, match="configured limit is 1"):
        service._check_raw_count(2)


def test_balance_raw_rows_use_physical_screen_boundary():
    from domains.reporting.models.simulation_analysis import (
        PhysicalRowsResult,
        PhysicalSimulationRow,
        QueryDiagnostics,
        SourceMetadata,
    )

    builder = SimpleNamespace()
    captured = {}

    def capture(_builder, headers, rows):
        captured["headers"] = headers
        captured["rows"] = list(rows)

    result = PhysicalRowsResult(
        rows=(
            PhysicalSimulationRow(
                observation_date=dt.date(2026, 1, 15),
                run_mode="simulation",
                valuation_type="eod",
                valuation_year=2026,
                valuation_month=1,
                gl_account="CASH",
                market=None,
                product=None,
                scenario="base",
                sample_index=0,
                supply_path=None,
                legal_entity=None,
                payment_year=2026,
                payment_month=1,
                value_usd=None,
                value_rub=1.5,
                volume=None,
            ),
        ),
        columns=("sample_index", "value_rub"),
        diagnostics=QueryDiagnostics("SELECT physical", SourceMetadata(True, False), 1),
    )
    service = SimulationAnalysisWorkbookService(lambda _query: result)
    service._write_raw_chunks = capture
    request = _request()
    request = SimulationAnalysisWorkbookRequest(
        **{**request.__dict__, "source_mode": "balance", "balance_tree_slug": "cash"}
    )

    service._add_raw_sheets(builder, request)

    assert captured == {
        "headers": ["sample_index", "value_rub"],
        "rows": [(0, 1.5)],
    }


@pytest.mark.parametrize("monthly_mode", ["monthly_net_cash_flow", "cumulative_cash_position"])
def test_monthly_actual_line_connects_to_first_forecast_median(monthly_mode):
    request = _request()
    monthly = [
        {
            "month": dt.date(2025, 12, 1),
            "values": [5.0],
            "statistics": {"P50": 5.0, "P10": 5.0, "P90": 5.0},
        },
        {
            "month": dt.date(2026, 1, 1),
            "values": [10.0, 20.0, 30.0],
            "statistics": {"P50": 20.0, "P10": 10.0, "P90": 30.0},
        },
        {
            "month": dt.date(2026, 2, 1),
            "values": [20.0, 30.0, 40.0],
            "statistics": {"P50": 30.0, "P10": 20.0, "P90": 40.0},
        },
    ]

    figure = SimulationPlotlyFigureSpecBuilder().build_monthly(
        monthly=monthly,
        observation_date=request.observation_date,
        period_mode=request.period_mode,
        target=request.target,
        monthly_mode=monthly_mode,
    )

    actual = next(trace for trace in figure.data if trace["name"] == "Факт")
    assert actual["x"] == ["дек. 2025 г.", "янв. 2026 г."]
    assert actual["y"] == [5.0, 20.0]
    assert figure.layout["shapes"][0]["x0"] == "янв. 2026 г."
    zero_lines = [shape for shape in figure.layout["shapes"] if shape["y0"] == shape["y1"] == 0]
    assert bool(zero_lines) is (monthly_mode == "cumulative_cash_position")


def test_plotly_python_consumes_builder_spec_without_workbook_mapping():
    spec = SimulationPlotlyFigureSpecBuilder().build_distribution(
        values=[10.0, 20.0, 30.0],
        x_grid=[10.0, 20.0, 30.0],
        density=[0.1, 0.2, 0.1],
        median=20.0,
        chart_type="density",
        period_mode="valuations",
        target="value_rub",
    )

    figure = go.Figure(spec.model_dump())

    assert figure.to_plotly_json()["data"] == spec.data
    assert figure.layout.xaxis.title.text == spec.layout["xaxis"]["title"]


@pytest.mark.parametrize("chart_type", ["box", "violin"])
def test_distribution_sample_spec_is_bounded_for_browser_and_kaleido(chart_type):
    builder = SimulationPlotlyFigureSpecBuilder()
    values = [float(value) for value in range(builder.MAX_DISTRIBUTION_SAMPLE_POINTS * 3)]

    spec = builder.build_distribution(
        values=values,
        x_grid=[],
        density=[],
        median=None,
        chart_type=chart_type,
        period_mode="valuations",
        target="value_rub",
    )

    assert len(spec.data[0]["y"]) == builder.MAX_DISTRIBUTION_SAMPLE_POINTS
    assert spec.data[0]["y"][0] == values[0]
    assert spec.data[0]["y"][-1] < values[-1]


def test_monthly_forecast_spec_has_one_shared_browser_point_budget():
    builder = SimulationPlotlyFigureSpecBuilder()
    values = [float(value) for value in range(10_000)]
    monthly = [
        {
            "month": dt.date(2026, month, 1),
            "values": values,
            "statistics": {"P50": 5_000.0, "P10": 1_000.0, "P90": 9_000.0},
        }
        for month in range(1, 5)
    ]

    spec = builder.build_monthly(
        monthly=monthly,
        observation_date=dt.date(2026, 1, 15),
        period_mode="payments",
        target="value_rub",
        monthly_mode="monthly_net_cash_flow",
    )

    forecasts = [trace for trace in spec.data if trace["name"] == "Прогноз"]
    assert len(forecasts) == len(monthly)
    assert sum(len(trace["y"]) for trace in forecasts) <= builder.MAX_MONTHLY_SAMPLE_POINTS
    assert [trace["x0"] for trace in forecasts] == spec.layout["xaxis"]["categoryarray"]
    assert all("x" not in trace for trace in forecasts)
    assert [trace["showlegend"] for trace in forecasts] == [True, False, False, False]
    encoded_month_labels = sum(
        str(trace).count(label)
        for trace in forecasts
        for label in spec.layout["xaxis"]["categoryarray"]
    )
    assert encoded_month_labels == len(monthly) * 2
