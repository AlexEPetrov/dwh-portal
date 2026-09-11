import datetime as dt
import uuid
from types import SimpleNamespace

from domains.risk.models.curve import (
    CurveAvailabilityModeEnum,
    CurveDefinition,
    CurvePointIntervalEnum,
    CurveTypeEnum,
)
from domains.risk.models.pricing import (
    ContractElement,
    CurveElement,
    Index,
    IndexElement,
    IndividualContractPricing,
)
from domains.risk.repositories.curve_data import CurveDataObjects
from domains.risk.repositories.curve_simulations_data import CurveSimulationDataObjects
from domains.risk.services.valuation.remote.required_objects import RequiredObjectsResolver
from proto.grpc_client import GRPCDataClient


def _curve(**kwargs):
    defaults = dict(
        id=uuid.uuid4(),
        name="TEST_FWD",
        slug="TEST_FWD",
        curve_type=CurveTypeEnum.FORWARD,
        point_interval=CurvePointIntervalEnum.MONTH,
        report_date_aheads=10,
        observ_date_aheads=3,
        availability_mode=CurveAvailabilityModeEnum.ROLLING_DAYS_WITH_INTERVAL_FLOOR,
    )
    defaults.update(kwargs)
    return CurveDefinition(**defaults)


def _row(observ_date, report_date, value=1.0, curve_name="TEST_FWD"):
    return SimpleNamespace(
        observ_date=observ_date,
        report_date=report_date,
        value=value,
        curve_name=curve_name,
        scenario_name="Базовый",
        extra_info=None,
        load_time=dt.datetime(2026, 1, 1, 12, 0),
    )


def test_materialize_effective_curve_points_preserves_sorted_effective_report_dates():
    curve = _curve()
    rows = [
        _row(dt.date(2026, 1, 5), dt.date(2026, 2, 1), 20.0),
        _row(dt.date(2026, 1, 5), dt.date(2026, 1, 1), 10.0),
    ]

    points = CurveDataObjects._materialize_effective_curve_points(
        curve,
        rows,
        dt.date(2026, 1, 1),
        dt.date(2026, 2, 3),
        report_date_aheads=720,
    )

    assert points
    assert [point[0] for point in points] == sorted(point[0] for point in points)
    assert points[0][0] == dt.date(2026, 1, 1).toordinal()
    assert points[-1][0] == dt.date(2026, 2, 3).toordinal()
    assert points[-1][2] == dt.date(2026, 2, 1).toordinal()


def test_grpc_conversion_preserves_effective_and_source_report_dates():
    effective_date = dt.date(2026, 2, 3)
    source_report_date = dt.date(2026, 2, 1)
    point = (
        effective_date.toordinal(),
        dt.date(2026, 1, 5).toordinal(),
        source_report_date.toordinal(),
        20.0,
        "TEST_FWD",
        "Базовый",
        None,
        dt.datetime(2026, 1, 1, 12, 0),
    )

    data_point = GRPCDataClient.__new__(GRPCDataClient)._convert_tuple_to_data_point(point)

    assert data_point.report_date == effective_date.toordinal()
    assert data_point.valuation_date == source_report_date.toordinal()


def test_send_data_batches_curves_and_keeps_final_empty_request(monkeypatch):
    calls = []

    class _Response:
        request_id = "req-1"
        status = "SUCCESS"
        message = "ok"
        processed_count = 0

    class _Stub:
        def SendCurveData(self, request):
            calls.append(request)
            return _Response()

    monkeypatch.setattr(
        "proto.grpc_client._create_channel", lambda target: SimpleNamespace(close=lambda: None)
    )
    monkeypatch.setattr("proto.grpc_client.pb2_grpc.CurveDataServiceStub", lambda channel: _Stub())

    client = GRPCDataClient("localhost:1")
    result = client.send_data(
        {
            ("A", dt.date(2026, 1, 1)): [
                (dt.date(2026, 1, 1), dt.date(2026, 1, 1), dt.date(2026, 1, 1), 1.0, "A", "")
            ],
            ("B", dt.date(2026, 1, 1)): [
                (dt.date(2026, 1, 2), dt.date(2026, 1, 1), dt.date(2026, 1, 2), 2.0, "B", "")
            ],
            ("C", dt.date(2026, 1, 1)): [
                (dt.date(2026, 1, 3), dt.date(2026, 1, 1), dt.date(2026, 1, 3), 3.0, "C", "")
            ],
        },
        request_id="req-1",
        curves_per_request=2,
    )

    assert [len(call.curves) for call in calls] == [2, 1, 0]
    assert result["curves_sent"] == 3
    assert result["points_sent"] == 3
    assert result["data_requests_sent"] == 2


def test_required_objects_resolver_collects_pricing_index_element_objects():
    nested = Index(
        name="NESTED_IDX",
        slug="NESTED_IDX",
        elements=[CurveElement(name="curve", curves=["CURVE_FROM_NESTED"])],
    )
    root = Index(
        name="ROOT_IDX",
        slug="ROOT_IDX",
        elements=[IndexElement(name="nested", indexes=[], index_objects=[nested])],
    )
    contract = SimpleNamespace(
        name="C1",
        slug="C1",
        pricing=[
            IndividualContractPricing(index=None, index_element=IndexElement(index_objects=[root]))
        ],
        deliveries=[],
        get_slug_or_name=lambda: "C1",
        pricing_uom="usd/1000m3",
    )
    data_context = SimpleNamespace(
        contracts=SimpleNamespace(get_all=lambda: [contract]),
        indexes=SimpleNamespace(
            get_first=lambda key: {"ROOT_IDX": root, "NESTED_IDX": nested}.get(key)
        ),
    )
    request = SimpleNamespace(contracts_ordered=[contract], reporting=SimpleNamespace(units=[]))

    required = RequiredObjectsResolver(data_context).resolve_deterministic(request)

    assert "ROOT_IDX" in required.index_keys
    assert "NESTED_IDX" in required.index_keys
    assert "CURVE_FROM_NESTED" in required.curve_keys


def test_required_objects_resolver_resolves_contractref_filter_expression():
    dependent_index = Index(
        name="DEPENDENT_IDX",
        slug="DEPENDENT_IDX",
        elements=[CurveElement(name="curve", curves=["DEPENDENT_CURVE"])],
    )
    root_index = Index(
        name="ROOT_WITH_CONTRACTREF",
        slug="ROOT_WITH_CONTRACTREF",
        elements=[ContractElement(name="dep", filter="contract://?group=dep", contracts=[])],
    )
    dependent_contract = SimpleNamespace(
        name="DEP",
        slug="DEP",
        pricing=[IndividualContractPricing(index="DEPENDENT_IDX")],
        deliveries=[],
        get_slug_or_name=lambda: "DEP",
        pricing_uom="usd/1000m3",
    )
    root_contract = SimpleNamespace(
        name="ROOT",
        slug="ROOT",
        pricing=[IndividualContractPricing(index="ROOT_WITH_CONTRACTREF")],
        deliveries=[],
        get_slug_or_name=lambda: "ROOT",
        pricing_uom="usd/1000m3",
    )

    class _ContractsRepo:
        def get_all(self):
            return [root_contract, dependent_contract]

        def where(self, params):
            assert params == {"group": "dep"}
            return [dependent_contract]

    data_context = SimpleNamespace(
        contracts=_ContractsRepo(),
        indexes=SimpleNamespace(
            get_first=lambda key: {
                "ROOT_WITH_CONTRACTREF": root_index,
                "DEPENDENT_IDX": dependent_index,
            }.get(key)
        ),
    )
    request = SimpleNamespace(
        contracts_ordered=[root_contract], reporting=SimpleNamespace(units=[])
    )

    required = RequiredObjectsResolver(data_context).resolve_deterministic(request)

    assert "ROOT" in required.contract_keys
    assert "DEP" in required.contract_keys
    assert "ROOT_WITH_CONTRACTREF" in required.index_keys
    assert "DEPENDENT_IDX" in required.index_keys
    assert "DEPENDENT_CURVE" in required.curve_keys


def test_simulation_history_preload_uses_shared_bulk_cache(monkeypatch):
    curve_a = _curve(name="A_FWD", slug="A_FWD")
    curve_b = _curve(name="B_FWD", slug="B_FWD")

    class _CurveDefinitions:
        def get_all(self):
            return [curve_a, curve_b]

    calls = []

    class _CacheableRepo:
        history_data = {}
        db_repository = SimpleNamespace(curve_def_repository=_CurveDefinitions())

        def cache_curves_bulk(
            self, observation_date, scenario, curves, min_date, max_date, overrides
        ):
            calls.append((observation_date, scenario, curves, min_date, max_date, overrides))
            self.history_data = {("A_FWD", observation_date): [(1, 1, 1, 10.0, "A_FWD", "")]}
            return SimpleNamespace(
                requested_curves=len(curves),
                loaded_curves=1,
                source_rows=1,
                materialized_points=1,
                elapsed_ms=1.0,
            )

    repo = _CacheableRepo()
    sim_repo = CurveSimulationDataObjects(repo)
    sim_repo._simulation_files = {"A_FWD": SimpleNamespace(), "B_FWD": SimpleNamespace()}
    observation_date = dt.date(2026, 1, 1)

    stats = sim_repo.preload_registered_history_curves_bulk(
        observation_date,
        None,
        dt.date(2026, 1, 1),
        [],
    )

    assert stats.requested_curves == 2
    assert len(calls) == 1
    assert [curve.get_slug_or_name() for curve in calls[0][2]] == ["A_FWD", "B_FWD"]
    assert CurveSimulationDataObjects.history_data[("A_FWD", observation_date)] == [
        (1, 1, 1, 10.0, "A_FWD", "")
    ]
