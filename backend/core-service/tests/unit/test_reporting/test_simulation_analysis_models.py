import datetime as dt

import pandas as pd
import pytest

from domains.reporting.models.simulation_analysis import (
    DateExpression,
    DimensionSelection,
    DynamicFilter,
    OperationIntent,
    PeriodMode,
    PeriodRange,
    ProjectionIntent,
    QueryIntent,
    ResolvedSimulationScope,
    SampleTargetSeries,
    SimulationAnalysisRequest,
    SourceMode,
    ValueTarget,
)
from domains.reporting.services.simulation_analysis import (
    FactSimulationReader,
    FilterSimulationAnalysisScopeResolver,
    SimulationAnalysisQueryDescriptor,
    SimulationAnalysisScopeError,
    SimulationAnalysisSqlBuilder,
)

OBSERVATION_DATE = dt.date(2026, 5, 8)
PERIOD = PeriodRange(dt.date(2026, 1, 1), dt.date(2026, 12, 31))


def request(**changes) -> SimulationAnalysisRequest:
    values = {
        "observation_date": OBSERVATION_DATE,
        "period": PERIOD,
        "period_mode": PeriodMode.VALUATIONS,
        "target": ValueTarget.VALUE_RUB,
    }
    values.update(changes)
    return SimulationAnalysisRequest(**values)


def test_resolved_scope_contains_request_and_date_expression() -> None:
    scope = ResolvedSimulationScope(request(), DateExpression.VALUATION_PERIOD)
    assert scope.request is not None
    assert scope.date_expression is DateExpression.VALUATION_PERIOD


def test_balance_request_requires_tree_slug() -> None:
    with pytest.raises(ValueError, match="balance_tree_slug"):
        request(source_mode=SourceMode.BALANCE)


def test_query_intent_rejects_invalid_projection() -> None:
    with pytest.raises(ValueError, match="invalid"):
        QueryIntent(OperationIntent.MONTHLY_FLOW, ProjectionIntent.SAMPLE_SET)


def test_sample_target_series_preserves_bulk_identity_contract() -> None:
    result = SampleTargetSeries((0, 1), (10.0, 20.0))

    assert result.sample_index == (0, 1)
    assert result.values == (10.0, 20.0)


def test_filter_scope_normalizes_identity_and_uses_payment_date() -> None:
    resolved = FilterSimulationAnalysisScopeResolver().resolve(
        request(
            valuation_type=" EOD ",
            period_mode=PeriodMode.PAYMENTS,
        )
    )
    assert resolved.request.valuation_type == "eod"
    assert resolved.date_expression.value == "payment_period"


def test_canonical_builder_uses_physical_payment_year_and_month_columns() -> None:
    scope = FilterSimulationAnalysisScopeResolver().resolve(
        request(period_mode=PeriodMode.PAYMENTS)
    )
    sql = SimulationAnalysisSqlBuilder().build(
        scope, QueryIntent(OperationIntent.COMBINED, ProjectionIntent.SAMPLE_SET)
    )
    assert "MAKE_DATE(CAST(payment_year AS INTEGER), CAST(payment_month AS INTEGER), 1)" in sql
    assert "payment_period" not in sql


def test_canonical_builder_uses_physical_valuation_year_and_month_columns() -> None:
    sql = SimulationAnalysisSqlBuilder().build(
        FilterSimulationAnalysisScopeResolver().resolve(request()),
        QueryIntent(OperationIntent.COMBINED, ProjectionIntent.SAMPLE_SET),
    )
    assert "MAKE_DATE(CAST(valuation_year AS INTEGER), CAST(valuation_month AS INTEGER), 1)" in sql
    assert "valuation_period" not in sql


def test_canonical_builder_excludes_cash_only_for_monthly_flow() -> None:
    scope = FilterSimulationAnalysisScopeResolver().resolve(request())
    builder = SimulationAnalysisSqlBuilder()
    monthly = builder.build(
        scope, QueryIntent(OperationIntent.MONTHLY_FLOW, ProjectionIntent.MONTHLY_PATHS)
    )
    full = builder.build(
        scope, QueryIntent(OperationIntent.FULL_POSITION, ProjectionIntent.MONTHLY_PATHS)
    )
    assert "gl_account <> 'AST_CASH_BALANCE'" in monthly
    assert "gl_account <> 'AST_CASH_BALANCE'" not in full


def test_canonical_full_position_reads_persisted_opening_cash_without_read_time_allocation() -> (
    None
):
    scope = FilterSimulationAnalysisScopeResolver().resolve(
        request(period_mode=PeriodMode.PAYMENTS)
    )
    sql = SimulationAnalysisSqlBuilder().build(
        scope, QueryIntent(OperationIntent.FULL_POSITION, ProjectionIntent.MONTHLY_PATHS)
    )
    assert "opening AS" in sql
    assert "payment_month IS NULL" in sql
    assert "value_rub / 12" not in sql
    assert "calculate_hybrid" not in sql


def test_monthly_path_query_retains_chart_path_columns_and_source_diagnostics() -> None:
    scope = FilterSimulationAnalysisScopeResolver().resolve(request())
    sql = SimulationAnalysisSqlBuilder().build(
        scope, QueryIntent(OperationIntent.MONTHLY_FLOW, ProjectionIntent.MONTHLY_PATHS)
    )
    assert "m.bucket_month AS month" in sql
    assert "u.sample_index" in sql
    assert "has_simulation" in sql and "has_static" in sql


def test_canonical_builder_uses_fact_simulation_price_components() -> None:
    scope = FilterSimulationAnalysisScopeResolver().resolve(request(target=ValueTarget.PRICE_RUB))
    sql = SimulationAnalysisSqlBuilder().build(
        scope,
        QueryIntent(OperationIntent.COMBINED, ProjectionIntent.SAMPLE_SET),
    )
    assert "SUM(value_rub) / NULLIF(SUM(volume), 0)" in sql
    assert "price_rub" not in sql


def test_canonical_builder_escapes_literals_and_rejects_identifiers() -> None:
    scope = FilterSimulationAnalysisScopeResolver().resolve(request(scenario="O'Reilly"))
    sql = SimulationAnalysisSqlBuilder().build(
        scope, QueryIntent(OperationIntent.COMBINED, ProjectionIntent.SAMPLE_SET)
    )
    assert "O''Reilly" in sql
    unsafe_scope = FilterSimulationAnalysisScopeResolver().resolve(
        request(dynamic_filters=(DynamicFilter("scenario; DROP TABLE x", "= 'base'"),))
    )
    with pytest.raises(SimulationAnalysisScopeError, match="unsafe SQL identifier"):
        SimulationAnalysisSqlBuilder().build(
            unsafe_scope, QueryIntent(OperationIntent.COMBINED, ProjectionIntent.SAMPLE_SET)
        )


def test_canonical_builder_normalizes_bare_dynamic_filter_values() -> None:
    scope = FilterSimulationAnalysisScopeResolver().resolve(
        request(dynamic_filters=(DynamicFilter("market", "sales_fabr"),))
    )
    sql = SimulationAnalysisSqlBuilder().build(
        scope, QueryIntent(OperationIntent.COMBINED, ProjectionIntent.SAMPLE_SET)
    )
    assert "market = 'sales_fabr'" in sql
    assert "market sales_fabr" not in sql


def test_canonical_builder_uses_supply_paths_as_dimensions() -> None:
    scope = FilterSimulationAnalysisScopeResolver().resolve(
        request(
            dimensions=DimensionSelection(supply_paths=("north", "south")),
        )
    )
    sql = SimulationAnalysisSqlBuilder().build(
        scope, QueryIntent(OperationIntent.COMBINED, ProjectionIntent.SAMPLE_SET)
    )
    assert "supply_path IN ('north', 'south')" in sql


def test_canonical_builder_preserves_dynamic_filter_operators() -> None:
    scope = FilterSimulationAnalysisScopeResolver().resolve(
        request(
            dynamic_filters=(
                DynamicFilter("market__eq", "sales_fabr, other_market"),
                DynamicFilter("product__contains", "gas"),
            )
        )
    )
    sql = SimulationAnalysisSqlBuilder().build(
        scope, QueryIntent(OperationIntent.COMBINED, ProjectionIntent.SAMPLE_SET)
    )
    assert "market IN ('sales_fabr', 'other_market')" in sql
    assert "product ILIKE '%gas%'" in sql


def test_reader_maps_ordered_samples_and_closes_connection() -> None:
    class Result:
        def fetchdf(self):
            return pd.DataFrame(
                {
                    "sample_index": [1, 0],
                    "target_value": [20.0, 10.0],
                    "has_simulation": [True, True],
                }
            )

    class Connection:
        closed = False

        def execute(self, _sql):
            return Result()

        def close(self):
            self.closed = True

    class Adapter:
        def __init__(self):
            self.connection = Connection()

        def valuation_hive_path_glob(self, **_kwargs):
            return "/facts/**/*.parquet"

        def to_duckdb_read_call(self, path, **_kwargs):
            return f"read_parquet('{path}')"

        def connect(self):
            return self.connection

    adapter = Adapter()
    result = FactSimulationReader(adapter).sample_set(
        SimulationAnalysisQueryDescriptor(
            "SELECT sample_index, target_value FROM simulation_data ORDER BY sample_index",
            OBSERVATION_DATE,
        )
    )
    assert [(item.sample_index, item.value) for item in result.samples] == [(1, 20.0), (0, 10.0)]
    assert result.diagnostics.row_count == 2
    assert adapter.connection.closed is True


def test_reader_iter_rows_is_bounded_and_closes_connection() -> None:
    class Cursor:
        description = [("sample_index",), ("target_value",)]

        def __init__(self):
            self.batches = [([(0, 1.0)],), ([(1, 2.0)],)]

        def fetchmany(self, size):
            assert size == 1
            return self.batches.pop(0)[0] if self.batches else []

    class Connection:
        closed = False
        cursor = Cursor()

        def execute(self, _sql):
            return self.cursor

        def close(self):
            self.closed = True

    class Adapter:
        connection = Connection()

        def valuation_hive_path_glob(self, **_kwargs):
            return "/facts/**/*.parquet"

        def to_duckdb_read_call(self, path, **_kwargs):
            return f"read_parquet('{path}')"

        def connect(self):
            return self.connection

    adapter = Adapter()
    batches = list(
        FactSimulationReader(adapter).iter_rows(
            SimulationAnalysisQueryDescriptor("SELECT * FROM simulation_data", OBSERVATION_DATE),
            chunk_size=1,
        )
    )
    assert batches == [
        (["sample_index", "target_value"], [[0, 1.0]]),
        (["sample_index", "target_value"], [[1, 2.0]]),
    ]
    assert adapter.connection.closed is True
