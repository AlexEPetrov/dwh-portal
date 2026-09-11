"""Unit tests for BalanceTreeService, including hybrid query logic."""

from __future__ import annotations

import datetime as dt
from unittest.mock import MagicMock
from uuid import uuid4

import numpy as np

from domains.management.models.gl_tree import GlTreeModel, GlTreeNodeModel, GlTreeOptionsModel
from domains.reporting.services.simulation_source_service import (
    BalanceMaterializationMismatchError,
    BalanceMaterializationNotFoundError,
    BalanceSimulationSourceRequest,
    BalanceSimulationSourceService,
    BalanceTreeNotFoundError,
    EmptyBalanceSimulationSourceError,
)
from domains.reporting.services.sql_query_service import FactQueryService
from domains.risk.services.balance.sources.modelled_balance_cell_resolver import (
    ModelledPositionService,
)
from domains.risk.services.balance.sources.monitored_balance_cell_resolver import (
    MonitoredPositionService,
)
from domains.risk.services.balance.tree.calculation.simulation_balance_tree import (
    BalanceTreeService,
)


def _make_tree(
    name: str,
    hierarchy: list[GlTreeNodeModel],
    year: int | None = 2026,
) -> GlTreeModel:
    return GlTreeModel(
        id=uuid4(),
        name=name,
        slug=name,
        options=GlTreeOptionsModel(year=year) if year else None,
        hierarchy=hierarchy,
    )


def _leaf(
    name: str,
    *,
    model_position: str | None = None,
    gl_account: str | None = None,
    market: str | None = None,
    product: str | None = None,
    data_source_type: str | None = "contract",
) -> GlTreeNodeModel:
    return GlTreeNodeModel(
        id=uuid4(),
        name=name,
        gl_account=gl_account,
        market=market,
        product=product,
        model_position=model_position,
        items=[],
        direction="ENTRY",
        data_source_type=data_source_type,
    )


def _make_service(sql_query: MagicMock | None = None) -> BalanceTreeService:
    """Build a BalanceTreeService with mocked deps (services not exercised here)."""
    return BalanceTreeService(
        monitored_position_service=MagicMock(spec=MonitoredPositionService),
        modelled_position_service=MagicMock(spec=ModelledPositionService),
        sql_query_service=sql_query or MagicMock(spec=FactQueryService),
    )


# ---------------------------------------------------------------------------
# Contracts filter collection
# ---------------------------------------------------------------------------


class TestCollectContractsFilters:
    def test_uses_legal_entity_field_for_persisted_node_filter(self):
        tree = _make_tree(
            "t",
            [
                _leaf(
                    "legal entity node",
                    model_position="internal://contracts?gl_account=REV",
                    gl_account="REV",
                )
            ],
        )
        tree.hierarchy[0].legal_entity = "LE-001"

        filters = _make_service()._collect_contracts_filters(tree.hierarchy)

        assert len(filters) == 1
        assert filters[0].legal_entity == "LE-001"

    def test_collects_filters_from_leaves(self):
        tree = _make_tree(
            "t",
            [
                _leaf("a", model_position="internal://contracts?gl_account=REV&market=m1"),
                _leaf("b", model_position="internal://contracts?gl_account=COST&product=p1"),
            ],
        )
        filters = _make_service()._collect_contracts_filters(tree.hierarchy)
        assert len(filters) == 2
        assert filters[0].gl_account == "REV"
        assert filters[0].market == "m1"
        assert filters[1].gl_account == "COST"
        assert filters[1].product == "p1"

    def test_ignores_constant_queries(self):
        tree = _make_tree(
            "t",
            [_leaf("a", model_position="internal://constant/42", data_source_type="const")],
        )
        filters = _make_service()._collect_contracts_filters(tree.hierarchy)
        assert filters == []

    def test_ignores_nodes_without_query(self):
        tree = _make_tree("t", [_leaf("a", model_position=None, data_source_type="none")])
        filters = _make_service()._collect_contracts_filters(tree.hierarchy)
        assert filters == []

    def test_recurses_into_children(self):
        tree = _make_tree(
            "t",
            [
                GlTreeNodeModel(
                    id=uuid4(),
                    name="parent",
                    items=[
                        _leaf("c", model_position="internal://contracts?gl_account=X"),
                    ],
                    direction="ENTRY",
                    data_source_type=None,
                )
            ],
        )
        filters = _make_service()._collect_contracts_filters(tree.hierarchy)
        assert len(filters) == 1
        assert filters[0].gl_account == "X"


# ---------------------------------------------------------------------------
# Hybrid query execution
# ---------------------------------------------------------------------------


class TestHybridQuery:
    def _build_service(self, mock_sql: MagicMock) -> BalanceTreeService:
        return _make_service(sql_query=mock_sql)

    def test_hybrid_query_executes_sql_through_sql_service(self):
        mock_sql = MagicMock()
        mock_sql.execute_query.return_value = (
            ["sample_index", "value_rub"],
            [[0, 1.5], [1, 2.5], [2, 3.5]],
            10.0,
        )
        svc = self._build_service(mock_sql)

        tree = _make_tree(
            "t",
            [_leaf("a", model_position="internal://contracts?gl_account=REV&market=m1")],
        )
        arr = svc.calculate_hybrid_simulation_tree(tree, dt.date(2026, 7, 3))

        assert isinstance(arr, np.ndarray)
        assert arr.tolist() == [1.5, 2.5, 3.5]
        mock_sql.execute_query.assert_called_once()

        _, kwargs = mock_sql.execute_query.call_args
        # SQL must contain both mc and static CTEs
        call_sql = kwargs["sql"] if "sql" in kwargs else mock_sql.execute_query.call_args[0][0]
        assert "mc_component" in call_sql
        assert "static_component" in call_sql
        assert "run_mode = 'simulation'" in call_sql
        assert "run_mode = 'static'" in call_sql
        assert "valuation_type = 'eod'" in call_sql
        # Static side is included by the same persisted-position filter.
        assert "static_component" in call_sql
        # Observation date formatted
        assert "20260703" in call_sql

    def test_hybrid_query_applies_requested_valuation_type_to_mc_and_static(self):
        mock_sql = MagicMock()
        mock_sql.execute_query.return_value = (["sample_index", "value_rub"], [], 0.0)
        svc = self._build_service(mock_sql)

        tree = _make_tree(
            "t",
            [_leaf("a", model_position="internal://contracts?gl_account=REV")],
        )
        svc.calculate_hybrid_simulation_tree(
            tree,
            dt.date(2026, 7, 3),
            valuation_type="custom1",
        )

        call_sql = mock_sql.execute_query.call_args[0][0]
        assert call_sql.count("valuation_type = 'custom1'") == 1
        assert "valuation_type = 'eod'" not in call_sql

    def test_hybrid_query_returns_values_for_simulation_analysis_balance_mode(self):
        mock_sql = MagicMock()
        mock_sql.execute_query.return_value = (
            ["sample_index", "value_rub"],
            [[0, 10.0], [1, 20.0], [2, 30.0]],
            1.0,
        )
        svc = self._build_service(mock_sql)

        tree = _make_tree(
            "t",
            [_leaf("a", model_position="internal://contracts?gl_account=REV")],
        )

        arr = svc.calculate_hybrid_simulation_tree(
            tree,
            dt.date(2026, 7, 3),
            scenario="base",
            valuation_type="eod",
        )

        assert arr.tolist() == [10.0, 20.0, 30.0]
        call_sql = mock_sql.execute_query.call_args[0][0]
        assert "hybrid_per_sample" in call_sql
        assert "ORDER BY sample_index" in call_sql

    def test_hybrid_query_applies_scenario_filter_to_mc_only(self):
        mock_sql = MagicMock()
        mock_sql.execute_query.return_value = (["sample_index", "value_rub"], [], 0.0)
        svc = self._build_service(mock_sql)

        tree = _make_tree(
            "t",
            [_leaf("a", model_position="internal://contracts?gl_account=REV")],
        )
        svc.calculate_hybrid_simulation_tree(tree, dt.date(2026, 7, 3), scenario="base")

        call_sql = mock_sql.execute_query.call_args[0][0]
        mc_component = call_sql.split("mc_component AS")[1].split("static_component AS")[0]
        static_component = call_sql.split("static_component AS")[1].split("sample_universe AS")[0]
        assert "scenario = 'base'" in mc_component
        assert "scenario = 'base'" not in static_component
        assert "scenario = 'default'" in static_component

    def test_hybrid_query_applies_year_filter(self):
        mock_sql = MagicMock()
        mock_sql.execute_query.return_value = (["sample_index", "value_rub"], [], 0.0)
        svc = self._build_service(mock_sql)

        tree = _make_tree(
            "t",
            [_leaf("a", model_position="internal://contracts?gl_account=REV")],
            year=2027,
        )
        svc.calculate_hybrid_simulation_tree(tree, dt.date(2027, 1, 1))

        call_sql = mock_sql.execute_query.call_args[0][0]
        assert "payment_year = 2027" in call_sql
        assert "valuation_year = 2027" not in call_sql

    def test_hybrid_query_returns_empty_when_no_filters(self):
        mock_sql = MagicMock()
        svc = self._build_service(mock_sql)
        tree = _make_tree("t", [_leaf("a", model_position=None, data_source_type="none")])
        arr = svc.calculate_hybrid_simulation_tree(tree, dt.date(2026, 7, 3))
        assert arr.size == 0
        mock_sql.execute_query.assert_called_once()

    def test_hybrid_query_returns_empty_on_sql_failure(self):
        mock_sql = MagicMock()
        mock_sql.execute_query.side_effect = RuntimeError("boom")
        svc = self._build_service(mock_sql)

        tree = _make_tree(
            "t",
            [_leaf("a", model_position="internal://contracts?gl_account=REV")],
        )
        arr = svc.calculate_hybrid_simulation_tree(tree, dt.date(2026, 7, 3))
        assert arr.size == 0

    def test_hybrid_query_does_not_apply_tree_dimension_filters(self):
        # Saved Balance reads the complete fact_simulation partition. Tree
        # dimensions describe the saved aggregation and are not a SQL scope.
        mock_sql = MagicMock()
        mock_sql.execute_query.return_value = (["sample_index", "value_rub"], [], 0.0)
        svc = self._build_service(mock_sql)

        tree = _make_tree(
            "t",
            [
                _leaf("a", model_position="internal://contracts?gl_account=REV"),
                _leaf("b", model_position="internal://contracts?gl_account=COST"),
            ],
        )
        svc.calculate_hybrid_simulation_tree(tree, dt.date(2026, 7, 3))

        call_sql = mock_sql.execute_query.call_args[0][0]
        assert "RE'V" not in call_sql or "REV" in call_sql
        assert "gl_account = 'REV'" not in call_sql
        assert "gl_account = 'COST'" not in call_sql
        assert "AND (TRUE)" in call_sql

    def test_hybrid_query_does_not_embed_tree_uri_dimensions(self):
        # Tree URI dimensions are intentionally not part of the saved Balance
        # SQL scope, so values requiring SQL escaping must not be embedded.
        mock_sql = MagicMock()
        mock_sql.execute_query.return_value = (["sample_index", "value_rub"], [], 0.0)
        svc = self._build_service(mock_sql)

        tree = _make_tree(
            "t",
            [_leaf("a", model_position="internal://contracts?gl_account=O'Brien")],
        )
        svc.calculate_hybrid_simulation_tree(tree, dt.date(2026, 7, 3))

        call_sql = mock_sql.execute_query.call_args[0][0]
        assert "O''Brien" not in call_sql
        assert "O'Brien" not in call_sql

    def test_hybrid_query_keeps_static_component_unfiltered_by_tree_filters(self):
        # Статическая часть должна оставаться полной и не сужаться фильтром узла.
        mock_sql = MagicMock()
        mock_sql.execute_query.return_value = (["sample_index", "value_rub"], [], 0.0)
        svc = self._build_service(mock_sql)

        tree = _make_tree(
            "t",
            [_leaf("a", model_position="internal://contracts?gl_account=REV&market=m1")],
        )
        svc.calculate_hybrid_simulation_tree(tree, dt.date(2026, 7, 3))

        call_sql = mock_sql.execute_query.call_args[0][0]
        static_component = call_sql.split("static_component AS")[1].split("sample_universe AS")[0]
        assert "WHERE gl_account = 'REV'" not in static_component
        assert "market = 'm1'" not in static_component
        assert "scenario = 'default'" in static_component

    def test_hybrid_monthly_query_uses_persisted_static_months_without_reallocation(self):
        # Месячный hybrid-запрос использует сохранённые месяцы без перераспределения.
        mock_sql = MagicMock()
        mock_sql.execute_query.return_value = (
            ["month", "sample_index", "value_rub"],
            [
                [dt.date(2026, 1, 1), 0, 10.0],
                [dt.date(2026, 1, 1), 1, 20.0],
                [dt.date(2026, 2, 1), 0, 30.0],
                [dt.date(2026, 2, 1), 1, 40.0],
            ],
            1.0,
        )
        svc = self._build_service(mock_sql)
        tree = _make_tree(
            "t",
            [_leaf("a", model_position="internal://contracts?gl_account=REV")],
            year=2026,
        )

        result = svc.calculate_hybrid_simulation_tree_monthly(
            tree,
            dt.date(2026, 7, 3),
            scenario="base",
            valuation_type="eod",
        )

        assert result == [
            {"month": "2026-01-01", "values": [10.0, 20.0]},
            {"month": "2026-02-01", "values": [30.0, 40.0]},
        ]
        call_sql = mock_sql.execute_query.call_args[0][0]
        assert "sample_index = -2" in call_sql
        assert "SELECT month FROM mc_component" in call_sql
        assert "SELECT month FROM static_component" in call_sql
        assert (
            "MAKE_DATE(CAST(payment_year AS INTEGER), CAST(payment_month AS INTEGER), 1)"
            in call_sql
        )
        assert "value_rub / 12.0" not in call_sql
        static_component = call_sql.split("static_component AS")[1].split("months AS")[0]
        assert "scenario = 'default'" in static_component


# ---------------------------------------------------------------------------
# Constructor
# ---------------------------------------------------------------------------


class TestConstructor:
    def test_construction_with_all_deps(self):
        mps = MagicMock(spec=MonitoredPositionService)
        mpos = MagicMock(spec=ModelledPositionService)
        fqs = MagicMock(spec=FactQueryService)
        svc = BalanceTreeService(mps, mpos, fqs)
        assert svc._monitored_position_service is mps
        assert svc._modelled_position_service is mpos
        assert svc._sql_query_service is fqs


class TestBalanceSimulationSourceService:
    def test_load_balance_samples_uses_saved_hive_path_when_metadata_matches(self):
        tree = _make_tree(
            "tree", [_leaf("a", model_position="internal://contracts?gl_account=REV")]
        )
        repo = MagicMock()
        repo.get_first.return_value = tree
        balance_tree_service = MagicMock()
        balance_tree_service.calculate_hybrid_simulation_tree.return_value = np.array([1.0, 2.0])
        metadata_service = MagicMock()
        metadata = MagicMock()
        metadata.balance_tree_slug = "tree"
        metadata_service.load.return_value = metadata

        service = BalanceSimulationSourceService(repo, balance_tree_service, metadata_service)
        result = service.load_balance_samples(
            BalanceSimulationSourceRequest(
                balance_tree_slug="tree",
                observation_date=dt.date(2026, 1, 1),
                scenario="base",
                valuation_type="eod",
            )
        )

        assert result.tolist() == [1.0, 2.0]
        balance_tree_service.calculate_hybrid_simulation_tree.assert_called_once_with(
            tree_def=tree,
            observation_date=dt.date(2026, 1, 1),
            scenario="base",
            valuation_type="eod",
        )
        balance_tree_service.calculate_simulation_tree.assert_not_called()

    def test_load_balance_samples_raises_when_metadata_missing_without_fallback(self):
        tree = _make_tree(
            "custom", [_leaf("a", model_position="internal://contracts?gl_account=REV")]
        )
        repo = MagicMock()
        repo.get_first.return_value = tree
        balance_tree_service = MagicMock()
        metadata_service = MagicMock()
        metadata_service.load.return_value = None

        service = BalanceSimulationSourceService(repo, balance_tree_service, metadata_service)
        try:
            service.load_balance_samples(
                BalanceSimulationSourceRequest(
                    balance_tree_slug="custom",
                    observation_date=dt.date(2026, 1, 1),
                    scenario=None,
                    valuation_type="eod",
                )
            )
        except BalanceMaterializationNotFoundError:
            pass
        else:
            raise AssertionError("Expected BalanceMaterializationNotFoundError")

        balance_tree_service.calculate_hybrid_simulation_tree.assert_not_called()
        balance_tree_service.calculate_simulation_tree.assert_not_called()

        balance_tree_service.build_hybrid_query_sql.return_value = "SELECT diagnostic_balance"
        trace = service.build_balance_sql_trace(
            BalanceSimulationSourceRequest(
                balance_tree_slug="custom",
                observation_date=dt.date(2026, 1, 1),
                scenario=None,
                valuation_type="eod",
            )
        )
        assert trace == "SELECT diagnostic_balance"
        balance_tree_service.build_hybrid_query_sql.assert_called_once_with(
            observation_date=dt.date(2026, 1, 1),
            filters=[],
            balance_year=2026,
            scenario=None,
            valuation_type="eod",
            filter_rules=None,
        )

    def test_load_balance_samples_raises_when_metadata_tree_mismatches(self):
        tree = _make_tree(
            "requested", [_leaf("a", model_position="internal://contracts?gl_account=REV")]
        )
        repo = MagicMock()
        repo.get_first.return_value = tree
        balance_tree_service = MagicMock()
        metadata_service = MagicMock()
        metadata = MagicMock()
        metadata.balance_tree_slug = "different"
        metadata_service.load.return_value = metadata

        service = BalanceSimulationSourceService(repo, balance_tree_service, metadata_service)
        try:
            service.load_balance_samples(
                BalanceSimulationSourceRequest(
                    balance_tree_slug="requested",
                    observation_date=dt.date(2026, 1, 1),
                    scenario=None,
                    valuation_type="eod",
                )
            )
        except BalanceMaterializationMismatchError:
            pass
        else:
            raise AssertionError("Expected BalanceMaterializationMismatchError")

        balance_tree_service.calculate_hybrid_simulation_tree.assert_not_called()
        balance_tree_service.calculate_simulation_tree.assert_not_called()

    def test_load_balance_monthly_samples_uses_hybrid_monthly_path_when_metadata_matches(self):
        tree = _make_tree(
            "tree", [_leaf("a", model_position="internal://contracts?gl_account=REV")]
        )
        repo = MagicMock()
        repo.get_first.return_value = tree
        balance_tree_service = MagicMock()
        balance_tree_service.calculate_hybrid_simulation_tree_monthly.return_value = [
            {"month": "2026-01-01", "values": [1.0, 2.0]}
        ]
        metadata_service = MagicMock()
        metadata = MagicMock()
        metadata.balance_tree_slug = "tree"
        metadata_service.load.return_value = metadata

        service = BalanceSimulationSourceService(repo, balance_tree_service, metadata_service)
        result = service.load_balance_monthly_samples(
            BalanceSimulationSourceRequest(
                balance_tree_slug="tree",
                observation_date=dt.date(2026, 1, 1),
                scenario="base",
                valuation_type="eod",
            )
        )

        assert result == [{"month": "2026-01-01", "values": [1.0, 2.0]}]
        balance_tree_service.calculate_hybrid_simulation_tree_monthly.assert_called_once()

    def test_load_balance_monthly_samples_raises_when_metadata_missing_without_allocation(self):
        tree = _make_tree(
            "custom", [_leaf("a", model_position="internal://contracts?gl_account=REV")]
        )
        repo = MagicMock()
        repo.get_first.return_value = tree
        balance_tree_service = MagicMock()
        metadata_service = MagicMock()
        metadata_service.load.return_value = None

        service = BalanceSimulationSourceService(repo, balance_tree_service, metadata_service)
        try:
            service.load_balance_monthly_samples(
                BalanceSimulationSourceRequest(
                    balance_tree_slug="custom",
                    observation_date=dt.date(2026, 1, 1),
                    scenario=None,
                    valuation_type="eod",
                )
            )
        except BalanceMaterializationNotFoundError:
            pass
        else:
            raise AssertionError("Expected BalanceMaterializationNotFoundError")

        balance_tree_service.calculate_hybrid_simulation_tree_monthly.assert_not_called()
        balance_tree_service.calculate_simulation_tree.assert_not_called()

    def test_load_balance_monthly_samples_raises_when_persisted_rows_empty(self):
        tree = _make_tree("tree", [_leaf("a")])
        repo = MagicMock()
        repo.get_first.return_value = tree
        balance_tree_service = MagicMock()
        balance_tree_service.calculate_hybrid_simulation_tree_monthly.return_value = []
        metadata_service = MagicMock()
        metadata = MagicMock()
        metadata.balance_tree_slug = "tree"
        metadata_service.load.return_value = metadata
        service = BalanceSimulationSourceService(repo, balance_tree_service, metadata_service)

        try:
            service.load_balance_monthly_samples(
                BalanceSimulationSourceRequest(
                    balance_tree_slug="tree",
                    observation_date=dt.date(2026, 1, 1),
                    scenario=None,
                    valuation_type="eod",
                )
            )
        except EmptyBalanceSimulationSourceError:
            return
        raise AssertionError("Expected EmptyBalanceSimulationSourceError")

    def test_resolve_balance_year_uses_tree_options_year(self):
        tree = _make_tree("tree", [_leaf("a")], year=2027)
        repo = MagicMock()
        repo.get_first.return_value = tree
        service = BalanceSimulationSourceService(repo, MagicMock(), MagicMock())

        result = service.resolve_balance_year(
            BalanceSimulationSourceRequest(
                balance_tree_slug="tree",
                observation_date=dt.date(2026, 7, 10),
                scenario=None,
                valuation_type="eod",
            )
        )

        assert result == 2027

    def test_load_balance_samples_raises_when_tree_missing(self):
        repo = MagicMock()
        repo.get_first.return_value = None
        service = BalanceSimulationSourceService(repo, MagicMock(), MagicMock())

        try:
            service.load_balance_samples(
                BalanceSimulationSourceRequest(
                    balance_tree_slug="missing",
                    observation_date=dt.date(2026, 1, 1),
                    scenario=None,
                    valuation_type="eod",
                )
            )
        except BalanceTreeNotFoundError:
            return
        raise AssertionError("Expected BalanceTreeNotFoundError")

    def test_load_balance_samples_raises_when_values_empty(self):
        repo = MagicMock()
        repo.get_first.return_value = _make_tree("tree", [_leaf("a")])
        balance_tree_service = MagicMock()
        balance_tree_service.calculate_hybrid_simulation_tree.return_value = np.array([])
        metadata_service = MagicMock()
        metadata = MagicMock()
        metadata.balance_tree_slug = "tree"
        metadata_service.load.return_value = metadata
        service = BalanceSimulationSourceService(repo, balance_tree_service, metadata_service)

        try:
            service.load_balance_samples(
                BalanceSimulationSourceRequest(
                    balance_tree_slug="tree",
                    observation_date=dt.date(2026, 1, 1),
                    scenario=None,
                    valuation_type=None,
                )
            )
        except EmptyBalanceSimulationSourceError:
            return
        raise AssertionError("Expected EmptyBalanceSimulationSourceError")
