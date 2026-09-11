"""Tests for the CQRS boundary around canonical Simulation Analysis reads."""

import datetime as dt

from domains.reporting.models.simulation_analysis import (
    DimensionSelection,
    OperationIntent,
    PeriodMode,
    PeriodRange,
    ProjectionIntent,
    QueryIntent,
    ResolvedSimulationScope,
    SimulationAnalysisRequest,
    SourceMode,
    ValueTarget,
)
from domains.reporting.queries.simulation_analysis import (
    CombinedSimulationAnalysisQuery,
    CombinedSimulationAnalysisQueryHandler,
    ComparisonSimulationAnalysisQuery,
    ComparisonSimulationAnalysisQueryHandler,
    DistributionSimulationAnalysisQueryHandler,
    LiquiditySimulationAnalysisQuery,
    LiquiditySimulationAnalysisQueryHandler,
    MonthlySimulationAnalysisQuery,
    MonthlySimulationAnalysisQueryHandler,
    PositionSimulationAnalysisQuery,
    PositionSimulationAnalysisQueryHandler,
    RawSimulationAnalysisQuery,
    RawSimulationAnalysisQueryHandler,
    SampleSeriesSimulationAnalysisQuery,
    SampleSeriesSimulationAnalysisQueryHandler,
    StatisticsSimulationAnalysisQueryHandler,
    WorkbookSimulationAnalysisQueryHandler,
)
from domains.reporting.services.simulation_analysis.scope import SimulationAnalysisScopeError

OBSERVATION_DATE = dt.date(2026, 5, 8)


class FakeResolver:
    def __init__(self, scope):
        self.scope = scope
        self.requests = []

    def resolve(self, request):
        self.requests.append(request)
        return self.scope


class FakeBuilder:
    def __init__(self):
        self.intents = []

    def build(self, scope, intent):
        self.intents.append(intent)
        return "SELECT 1"


class FakeReader:
    def __init__(self):
        self.descriptors = []

    def monthly_paths(self, descriptor):
        self.descriptors.append(descriptor)
        return "monthly-result"

    def physical_rows(self, descriptor):
        self.descriptors.append(descriptor)
        return "physical-result"

    def sample_set(self, descriptor):
        self.descriptors.append(descriptor)
        return "sample-result"

    def sample_series(self, descriptor):
        self.descriptors.append(descriptor)
        return "sample-series-result"


def _request():
    return SimulationAnalysisRequest(
        observation_date=OBSERVATION_DATE,
        period=PeriodRange(dt.date(2026, 1, 1), dt.date(2026, 12, 31)),
        period_mode=PeriodMode.PAYMENTS,
        target=ValueTarget.VALUE_RUB,
        source_mode=SourceMode.FILTER,
        dimensions=DimensionSelection(),
    )


def _scope():
    request = _request()
    from domains.reporting.models.simulation_analysis import DateExpression

    return ResolvedSimulationScope(
        request,
        DateExpression.PAYMENT_PERIOD,
    )


def test_monthly_handler_delegates_monthly_intent_and_reader():
    resolver, builder, reader = FakeResolver(_scope()), FakeBuilder(), FakeReader()
    result = MonthlySimulationAnalysisQueryHandler(
        None, source_resolver=resolver, builder=builder, reader=reader
    ).execute(MonthlySimulationAnalysisQuery(request=_request()))

    assert result == "monthly-result"
    assert builder.intents == [QueryIntent("monthly_flow", ProjectionIntent.MONTHLY_PATHS)]
    assert resolver.requests == [_request()]


def test_position_handler_delegates_full_position_paths_to_reader():
    resolver, builder, reader = FakeResolver(_scope()), FakeBuilder(), FakeReader()
    result = PositionSimulationAnalysisQueryHandler(
        None, source_resolver=resolver, builder=builder, reader=reader
    ).execute(PositionSimulationAnalysisQuery(request=_request()))

    assert result == "monthly-result"
    assert builder.intents == [QueryIntent("full_position", ProjectionIntent.MONTHLY_PATHS)]


def test_sample_series_handler_delegates_bulk_projection_and_reader():
    resolver, builder, reader = FakeResolver(_scope()), FakeBuilder(), FakeReader()
    result = SampleSeriesSimulationAnalysisQueryHandler(
        None, source_resolver=resolver, builder=builder, reader=reader
    ).execute(SampleSeriesSimulationAnalysisQuery(request=_request()))

    assert result == "sample-series-result"
    assert builder.intents == [
        QueryIntent(OperationIntent.COMBINED, ProjectionIntent.SAMPLE_SERIES)
    ]


def test_position_and_liquidity_share_full_position_boundary_without_opening_injection():
    assert (
        PositionSimulationAnalysisQueryHandler.operation
        is LiquiditySimulationAnalysisQueryHandler.operation
    )
    assert (
        PositionSimulationAnalysisQueryHandler.projection
        is LiquiditySimulationAnalysisQueryHandler.projection
    )
    assert PositionSimulationAnalysisQueryHandler.operation is OperationIntent.FULL_POSITION
    assert PositionSimulationAnalysisQueryHandler.projection is ProjectionIntent.MONTHLY_PATHS

    resolver, builder, reader = FakeResolver(_scope()), FakeBuilder(), FakeReader()
    LiquiditySimulationAnalysisQueryHandler(
        None, source_resolver=resolver, builder=builder, reader=reader
    ).execute(LiquiditySimulationAnalysisQuery(request=_request()))
    assert builder.intents == [
        QueryIntent(OperationIntent.FULL_POSITION, ProjectionIntent.MONTHLY_PATHS)
    ]


def test_raw_handler_uses_physical_rows_without_derived_projection():
    resolver, builder, reader = FakeResolver(_scope()), FakeBuilder(), FakeReader()
    result = RawSimulationAnalysisQueryHandler(
        None, source_resolver=resolver, builder=builder, reader=reader
    ).execute(RawSimulationAnalysisQuery(request=_request()))

    assert result == "physical-result"
    assert builder.intents == [QueryIntent("physical_raw", ProjectionIntent.PHYSICAL_ROWS)]
    assert reader.descriptors[0].sql == "SELECT 1"


def test_all_query_handlers_declare_canonical_intents():
    expected = {
        CombinedSimulationAnalysisQueryHandler: ("combined", "sample_set"),
        StatisticsSimulationAnalysisQueryHandler: ("combined", "statistics"),
        DistributionSimulationAnalysisQueryHandler: ("combined", "sample_set"),
        MonthlySimulationAnalysisQueryHandler: ("monthly_flow", "monthly_paths"),
        PositionSimulationAnalysisQueryHandler: ("full_position", "monthly_paths"),
        LiquiditySimulationAnalysisQueryHandler: ("full_position", "monthly_paths"),
        RawSimulationAnalysisQueryHandler: ("physical_raw", "physical_rows"),
        WorkbookSimulationAnalysisQueryHandler: ("physical_raw", "physical_rows"),
    }

    for handler_type, (operation, projection) in expected.items():
        assert handler_type.operation.value == operation
        assert handler_type.projection.value == projection


def test_handler_propagates_source_domain_errors_before_building_sql():
    class RejectingResolver:
        def resolve(self, request):
            raise SimulationAnalysisScopeError("invalid persisted scope")

    builder = FakeBuilder()
    reader = FakeReader()
    handler = CombinedSimulationAnalysisQueryHandler(
        None, source_resolver=RejectingResolver(), builder=builder, reader=reader
    )

    import pytest

    with pytest.raises(SimulationAnalysisScopeError, match="invalid persisted scope"):
        handler.execute(CombinedSimulationAnalysisQuery(request=_request()))
    assert builder.intents == []
    assert reader.descriptors == []


def test_comparison_handler_resolves_each_observation_date_independently():
    resolver = FakeResolver(_scope())
    builder, reader = FakeBuilder(), FakeReader()
    batch = ComparisonSimulationAnalysisQuery(
        batch={
            "request": _request(),
            "observation_dates": (OBSERVATION_DATE, OBSERVATION_DATE + dt.timedelta(days=1)),
        }
    )

    result = ComparisonSimulationAnalysisQueryHandler(
        None, source_resolver=resolver, builder=builder, reader=reader
    ).execute(batch)

    assert len(result.slices) == 2
    assert [request.observation_date for request in resolver.requests] == [
        OBSERVATION_DATE,
        OBSERVATION_DATE + dt.timedelta(days=1),
    ]
    assert len(reader.descriptors) == 2
