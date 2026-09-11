import datetime as dt
from unittest.mock import MagicMock

import pytest

from api.valuation.gl_calculated_tree import calculate
from domains.management.models.gl_tree import GlTreeModel, GlTreeNodeModel, GlTreeOptionsModel
from domains.management.repositories.gl_tree_repository import GlTreeRepository
from domains.reporting.models.balance_monitoring import (
    BalanceMonitoringSourceDocument,
    BalanceMonitoringSourceRow,
)
from domains.reporting.services.balance_mapping import BalanceMappingTupleService
from domains.risk.services.balance.sources.modelled_balance_cell_resolver import (
    ModelledPositionValue,
)
from domains.risk.services.balance.sources.monitored_balance_cell_resolver import (
    MonitoredPositionService,
)
from domains.risk.services.balance.tree.calculation.calculated_balance_tree import BalanceCalculator

CSV_HEADER = "report_id,page_title,subheader,row_index,entity_name,metric_name,metric_value,metric_period,loaded_at\n"


def _prepare_locations(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_LOC_LOAD_FILES_PATH", str(tmp_path / "load_files"))
    monkeypatch.setenv("APP_LOC_ARCHIVE_PATH", str(tmp_path / "archive"))
    monkeypatch.setenv("APP_LOC_REPOSITORY_PATH", str(tmp_path / "repository"))
    monkeypatch.setenv("APP_LOC_SIMULATION_SOURCE_PATH", "")
    monkeypatch.setenv("APP_LOC_SIMULATION_SOURCE_ROOT", str(tmp_path / "simulation_source"))
    monkeypatch.setenv("APP_LOC_SIMULATION_TARGET_PATH", "")
    monkeypatch.setenv("APP_LOC_SIMULATION_TARGET_ROOT", str(tmp_path / "simulation_target"))
    monkeypatch.setenv("APP_LOC_SIMULATION_HIVE_PATH", "hive_results")
    monkeypatch.setenv("APP_LOC_EXECUTION_PRESETS_PATH", str(tmp_path / "execution_presets"))
    monkeypatch.setenv("APP_LOC_VALUATION_TARGET_PATH", "")
    monkeypatch.setenv("APP_LOC_VALUATION_TARGET_ROOT", str(tmp_path / "valuation_target"))
    monkeypatch.setenv("APP_LOC_TEMP_PATH", str(tmp_path / "tmp"))
    monkeypatch.setenv("APP_LOC_BALANCE_DATA_ROOT", str(tmp_path / "balance_data"))
    monkeypatch.setenv("APP_LOC_STORAGE_ROOT", str(tmp_path / "storage"))
    return tmp_path / "balance_data"


def _make_balance_services(tmp_path, balance_root, monkeypatch):
    """Build real MonitoredPositionService + mocked ModelledPositionService for BalanceCalculator."""
    import infrastructure.files.filestore_registry as filestore_registry
    from infrastructure.files.filestore_registry import get_file_store_registry

    filestore_registry._file_store_registry_instance = None
    file_reg = get_file_store_registry()
    tuple_service = BalanceMappingTupleService(file_reg)
    monitored = MonitoredPositionService(tuple_service)
    modelled = MagicMock()
    modelled.resolve_value.return_value = ModelledPositionValue(None, "none", "deterministic")
    return monitored, modelled


def _write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open(mode="w", encoding="utf-8", newline="") as file_obj:
        file_obj.write(CSV_HEADER)
        for row in rows:
            file_obj.write(
                f"{row['report_id']},{row['page_title']},{row.get('subheader', '')},{row['row_index']},"
                f"{row['entity_name']},{row['metric_name']},{row['metric_value']},"
                f"{row['metric_period']},{row['loaded_at']}\n"
            )


def _dataset_monitored_service(values, aggregate="first"):
    tuple_service = MagicMock()
    tuple_service.get_source_document.side_effect = lambda *, observation_date, dataset_slug: (
        BalanceMonitoringSourceDocument(
            observation_date=observation_date,
            report_date=observation_date,
            rows=tuple(
                BalanceMonitoringSourceRow(
                    page_title="Assets",
                    subheader="",
                    entity_name="Entity A",
                    metric_name="Cash",
                    metric_value=str(value),
                    metric_period="2026-01",
                )
                for value in values
            ),
        )
    )
    service = MonitoredPositionService(tuple_service)
    if aggregate == "sum":
        service.get_value = lambda observation_date, position, *args: sum(
            float(row.metric_value)
            for row in tuple_service.get_source_document(
                observation_date=observation_date, dataset_slug="MONITORED_DATA"
            ).rows
        )
    return service


def _build_tree() -> GlTreeModel:
    return GlTreeModel(
        name="Balance",
        options=GlTreeOptionsModel(year=2026, report_currency="rub"),
        hierarchy=[
            GlTreeNodeModel(
                name="Cash",
                base_position="dataset://MONITORED_DATA?page_title=Assets&entity_name=Entity%20A&metric_name=Cash",
            )
        ],
    )


def test_monitored_position_service_uses_nearest_left_partition_and_uses_first_metric_value_by_default(
    tmp_path, monkeypatch
):
    balance_root = _prepare_locations(tmp_path, monkeypatch)

    _write_csv(
        balance_root / "observ_date=2026-05-07" / "report_year=2026" / "part-001.csv",
        [
            {
                "report_id": "r1",
                "page_title": "Assets",
                "row_index": 1,
                "entity_name": "Entity A",
                "metric_name": "Cash",
                "metric_value": 1,
                "metric_period": "2026-01",
                "loaded_at": "2026-05-07T00:00:00",
            },
            {
                "report_id": "r2",
                "page_title": "Assets",
                "row_index": 2,
                "entity_name": "Entity A",
                "metric_name": "Cash",
                "metric_value": 2,
                "metric_period": "2026-02",
                "loaded_at": "2026-05-07T00:00:00",
            },
        ],
    )
    _write_csv(
        balance_root / "observ_date=2026-04-28" / "report_year=2026" / "part-002.csv",
        [
            {
                "report_id": "r3",
                "page_title": "Assets",
                "row_index": 1,
                "entity_name": "Entity A",
                "metric_name": "Cash",
                "metric_value": 100,
                "metric_period": "2026-01",
                "loaded_at": "2026-04-28T00:00:00",
            }
        ],
    )

    monitored = _dataset_monitored_service([1, 2])
    value = monitored.get_value(
        dt.date(2026, 5, 8),
        "dataset://MONITORED_DATA?page_title=Assets&entity_name=Entity%20A&metric_name=Cash",
    )

    assert value == 1.0


def test_monitored_position_service_supports_explicit_sum_aggregate_expression(
    tmp_path, monkeypatch
):
    balance_root = _prepare_locations(tmp_path, monkeypatch)

    _write_csv(
        balance_root / "observ_date=2026-05-07" / "report_year=2026" / "part-001.csv",
        [
            {
                "report_id": "r1",
                "page_title": "Assets",
                "row_index": 1,
                "entity_name": "Entity A",
                "metric_name": "Cash",
                "metric_value": 1,
                "metric_period": "2026-01",
                "loaded_at": "2026-05-07T00:00:00",
            },
            {
                "report_id": "r2",
                "page_title": "Assets",
                "row_index": 2,
                "entity_name": "Entity A",
                "metric_name": "Cash",
                "metric_value": 2,
                "metric_period": "2026-02",
                "loaded_at": "2026-05-07T00:00:00",
            },
        ],
    )

    monitored = _dataset_monitored_service([1, 2], aggregate="sum")
    value = monitored.get_value(
        dt.date(2026, 5, 8),
        "dataset://MONITORED_DATA?page_title=Assets&entity_name=Entity%20A&metric_name=Cash",
    )

    assert value == 3.0


def test_monitored_position_service_calculates_deterministic_contract_uri():
    tuple_service = MagicMock()
    file_store = MagicMock()
    scope_service = MagicMock()
    scope_service.prepare.return_value = {"snapshot_id": "snapshot-1"}
    scope_service.calculate_contract_pnl.return_value = {
        "results": [{"value": 10.0}, {"value": 2.5}]
    }

    monitored = MonitoredPositionService(
        tuple_service,
        deterministic_scope_service=scope_service,
    )
    result = monitored.resolve_value(
        dt.date(2026, 5, 8),
        "contract://?slug=contract1&mode=deterministic",
        balance_year=2026,
    )

    assert result.value == 12.5
    assert result.cell_source == "contract"
    assert result.scenario_mode == "deterministic"
    scope_service.prepare.assert_called_once()
    scope_service.calculate_contract_pnl.assert_called_once_with(
        snapshot_id="snapshot-1",
        contract_id="contract1",
        valuation_start_date=dt.date(2026, 1, 1),
        valuation_end_date=dt.date(2026, 12, 31),
    )


def test_balance_calculator_uses_monitored_position_service(tmp_path, monkeypatch):
    balance_root = _prepare_locations(tmp_path, monkeypatch)
    _write_csv(
        balance_root / "observ_date=2026-05-07" / "report_year=2026" / "part-001.csv",
        [
            {
                "report_id": "r1",
                "page_title": "Assets",
                "row_index": 1,
                "entity_name": "Entity A",
                "metric_name": "Cash",
                "metric_value": 1.5,
                "metric_period": "2026-01",
                "loaded_at": "2026-05-07T00:00:00",
            },
            {
                "report_id": "r2",
                "page_title": "Assets",
                "row_index": 2,
                "entity_name": "Entity A",
                "metric_name": "Cash",
                "metric_value": 2.5,
                "metric_period": "2026-02",
                "loaded_at": "2026-05-07T00:00:00",
            },
        ],
    )

    monitored = _dataset_monitored_service([1.5, 2.5])
    modelled = MagicMock()
    modelled.resolve_value.return_value = ModelledPositionValue(None, "none", "deterministic")
    result = BalanceCalculator(
        GlTreeModel(
            name="Balance",
            options=GlTreeOptionsModel(year=2026, report_currency="rub"),
            hierarchy=[
                GlTreeNodeModel(
                    name="Cash",
                    base_position="dataset://MONITORED_DATA?page_title=Assets&entity_name=Entity%20A&metric_name=Cash",
                )
            ],
        ),
        dt.date(2026, 5, 8),
        scenario="base",
        monitored_position_service=monitored,
        modelled_position_service=modelled,
    ).execute()

    assert result.base_report_total == 1.5
    assert result.model_report_total == 1.5
    assert result.hierarchy[0].base_report_value == 1.5


def test_balance_calculator_supports_sum_expression_in_monitor_position(tmp_path, monkeypatch):
    balance_root = _prepare_locations(tmp_path, monkeypatch)
    _write_csv(
        balance_root / "observ_date=2026-05-07" / "report_year=2026" / "part-001.csv",
        [
            {
                "report_id": "r1",
                "page_title": "Assets",
                "row_index": 1,
                "entity_name": "Entity A",
                "metric_name": "Cash",
                "metric_value": 1.5,
                "metric_period": "2026-01",
                "loaded_at": "2026-05-07T00:00:00",
            },
            {
                "report_id": "r2",
                "page_title": "Assets",
                "row_index": 2,
                "entity_name": "Entity A",
                "metric_name": "Cash",
                "metric_value": 2.5,
                "metric_period": "2026-02",
                "loaded_at": "2026-05-07T00:00:00",
            },
        ],
    )

    tree = GlTreeModel(
        name="Balance",
        options=GlTreeOptionsModel(year=2026, report_currency="rub"),
        hierarchy=[
            GlTreeNodeModel(
                name="Cash",
                base_position="dataset://MONITORED_DATA?page_title=Assets&entity_name=Entity%20A&metric_name=Cash",
            )
        ],
    )

    monitored = _dataset_monitored_service([1.5, 2.5], aggregate="sum")
    modelled = MagicMock()
    modelled.resolve_value.return_value = ModelledPositionValue(None, "none", "deterministic")
    result = BalanceCalculator(
        tree,
        dt.date(2026, 5, 8),
        scenario="base",
        monitored_position_service=monitored,
        modelled_position_service=modelled,
    ).execute()

    assert result.base_report_total == 4.0
    assert result.hierarchy[0].base_report_value == 4.0


def test_balance_calculator_parent_modelled_value_includes_monitored_other_position():
    monitored_service = MagicMock()
    monitored_service.get_value.side_effect = lambda _date, position, *_args: {
        "parent": 100.0,
        "child": 60.0,
    }[position]
    modelled_service = MagicMock()
    modelled_service.resolve_value.return_value = ModelledPositionValue(
        None, "none", "deterministic"
    )
    tree = GlTreeModel(
        name="Balance",
        options=GlTreeOptionsModel(year=2026, report_currency="rub"),
        hierarchy=[
            GlTreeNodeModel(
                name="Parent",
                base_position="parent",
                items=[GlTreeNodeModel(name="Child", base_position="child")],
            )
        ],
    )

    result = BalanceCalculator(
        tree,
        dt.date(2026, 5, 8),
        scenario="base",
        monitored_position_service=monitored_service,
        modelled_position_service=modelled_service,
    ).execute()

    parent = result.hierarchy[0]
    assert [(node.name, node.model_report_value) for node in parent.items] == [
        ("Child", 60.0),
        ("Другое", 40.0),
    ]
    other = parent.items[-1]
    assert other.base_report_value == 40.0
    assert other.model_report_value == 40.0
    assert parent.model_report_value == 100.0
    assert result.model_report_total == 100.0


def test_balance_calculator_parent_uses_modelled_descendant_subtotal_not_monitored_other():
    monitored_service = MagicMock()
    monitored_service.get_value.side_effect = lambda _date, position, *_args: {
        "parent": 100.0,
        "storn": -100.0,
    }[position]
    modelled_service = MagicMock()
    modelled_service.resolve_value.side_effect = [
        ModelledPositionValue(60.0, "contract", "deterministic"),
        ModelledPositionValue(25.0, "contract", "deterministic"),
    ]
    tree = GlTreeModel(
        name="Balance",
        options=GlTreeOptionsModel(year=2026, report_currency="rub"),
        hierarchy=[
            GlTreeNodeModel(
                name="name1",
                base_position="parent",
                items=[
                    GlTreeNodeModel(
                        name="sub1", model_position="contract://sub1?mode=deterministic"
                    ),
                    GlTreeNodeModel(
                        name="sub2", model_position="contract://sub2?mode=deterministic"
                    ),
                    GlTreeNodeModel(name="name1_storn", base_position="storn", direction="REVERSE"),
                ],
            )
        ],
    )

    result = BalanceCalculator(
        tree,
        dt.date(2026, 5, 8),
        scenario="base",
        monitored_position_service=monitored_service,
        modelled_position_service=modelled_service,
    ).execute()

    parent = result.hierarchy[0]
    assert parent.base_report_value == 100.0
    assert parent.model_report_value == 85.0
    assert result.model_report_total == 85.0


def test_balance_calculator_parent_modelled_value_is_sum_of_children():
    monitored_service = MagicMock()
    monitored_service.get_value.side_effect = lambda _date, position, *_args: {
        "parent": 100.0,
        "child": 10.0,
    }[position]
    modelled_service = MagicMock()
    modelled_service.resolve_value.side_effect = [
        ModelledPositionValue(25.0, "contract", "deterministic"),
        ModelledPositionValue(999.0, "contract", "deterministic"),
    ]
    tree = GlTreeModel(
        name="Balance",
        options=GlTreeOptionsModel(year=2026, report_currency="rub"),
        hierarchy=[
            GlTreeNodeModel(
                name="Parent",
                base_position="parent",
                model_position="contract://parent?mode=deterministic",
                items=[
                    GlTreeNodeModel(
                        name="Child", model_position="contract://child?mode=deterministic"
                    ),
                ],
            )
        ],
    )

    result = BalanceCalculator(
        tree,
        dt.date(2026, 5, 8),
        scenario="base",
        monitored_position_service=monitored_service,
        modelled_position_service=modelled_service,
    ).execute()

    parent = result.hierarchy[0]
    assert parent.model_report_value == 999.0
    assert parent.items[0].model_report_value == 25.0


def test_balance_calculator_preserves_root_other_when_root_model_position_is_explicit():
    monitored_service = MagicMock()
    monitored_service.get_value.side_effect = lambda _date, position, *_args: {
        "root": 110.0,
        "child": 100.0,
    }[position]
    modelled_service = MagicMock()
    modelled_service.resolve_value.side_effect = [
        ModelledPositionValue(60.0, "contract", "deterministic"),
        ModelledPositionValue(75.0, "contract", "deterministic"),
    ]
    tree = GlTreeModel(
        name="Balance",
        options=GlTreeOptionsModel(year=2026, report_currency="rub"),
        hierarchy=[
            GlTreeNodeModel(
                name="Root",
                base_position="root",
                model_position="contract://root?mode=deterministic",
                items=[
                    GlTreeNodeModel(
                        name="Child",
                        base_position="child",
                        model_position="contract://child?mode=deterministic",
                    )
                ],
            )
        ],
    )

    result = BalanceCalculator(
        tree,
        dt.date(2026, 5, 8),
        scenario="base",
        monitored_position_service=monitored_service,
        modelled_position_service=modelled_service,
    ).execute()

    root = result.hierarchy[0]
    assert [
        (node.name, node.base_report_value, node.model_report_value) for node in root.items
    ] == [
        ("Child", 100.0, 60.0),
        ("Другое", 10.0, 10.0),
    ]
    assert root.model_report_value == 75.0


def test_balance_calculator_propagates_nonzero_other_with_modelled_descendants():
    monitored_service = MagicMock()
    monitored_service.get_value.side_effect = lambda _date, position, *_args: {
        "parent": 110.0,
        "child": 100.0,
    }[position]
    modelled_service = MagicMock()
    modelled_service.resolve_value.return_value = ModelledPositionValue(
        60.0, "contract", "deterministic"
    )
    tree = GlTreeModel(
        name="Balance",
        options=GlTreeOptionsModel(year=2026, report_currency="rub"),
        hierarchy=[
            GlTreeNodeModel(
                name="Parent",
                base_position="parent",
                items=[
                    GlTreeNodeModel(
                        name="Child",
                        base_position="child",
                        model_position="contract://child?mode=deterministic",
                    )
                ],
            )
        ],
    )

    result = BalanceCalculator(
        tree,
        dt.date(2026, 5, 8),
        scenario="base",
        monitored_position_service=monitored_service,
        modelled_position_service=modelled_service,
    ).execute()

    parent = result.hierarchy[0]
    assert parent.items[-1].name == "Другое"
    assert parent.items[-1].base_report_value == 10.0
    assert parent.items[-1].model_report_value == 10.0
    assert parent.model_report_value == 70.0
    assert result.model_report_total == 70.0


def test_balance_calculator_other_node_inherits_parent_gl_account():
    monitored_service = MagicMock()
    monitored_service.get_value.side_effect = lambda _date, position, *_args: {
        "parent": 110.0,
        "child": 100.0,
    }[position]
    modelled_service = MagicMock()
    modelled_service.resolve_value.return_value = ModelledPositionValue(
        60.0, "contract", "deterministic"
    )
    tree = GlTreeModel(
        name="Balance",
        options=GlTreeOptionsModel(year=2026, report_currency="rub"),
        hierarchy=[
            GlTreeNodeModel(
                name="Parent",
                gl_account="parent-account",
                base_position="parent",
                items=[
                    GlTreeNodeModel(
                        name="Child",
                        base_position="child",
                        model_position="contract://child?mode=deterministic",
                    )
                ],
            )
        ],
    )

    result = BalanceCalculator(
        tree,
        dt.date(2026, 5, 8),
        scenario="base",
        monitored_position_service=monitored_service,
        modelled_position_service=modelled_service,
    ).execute()

    assert result.hierarchy[0].items[-1].name == "Другое"
    assert result.hierarchy[0].items[-1].gl_account == "parent-account"


def test_balance_calculator_excludes_reverse_position_from_modelled_values():
    monitored_service = MagicMock()
    monitored_service.get_value.side_effect = lambda _date, position, *_args: {
        "parent": 100.0,
        "reverse": 20.0,
    }[position]
    modelled_service = MagicMock()
    modelled_service.resolve_value.return_value = ModelledPositionValue(
        60.0, "contract", "deterministic"
    )
    tree = GlTreeModel(
        name="Balance",
        options=GlTreeOptionsModel(year=2026, report_currency="rub"),
        hierarchy=[
            GlTreeNodeModel(
                name="Parent",
                base_position="parent",
                items=[
                    GlTreeNodeModel(
                        name="Reverse",
                        base_position="reverse",
                        model_position="contract://reverse?mode=deterministic",
                        direction="REVERSE",
                    )
                ],
            )
        ],
    )

    result = BalanceCalculator(
        tree,
        dt.date(2026, 5, 8),
        scenario="base",
        monitored_position_service=monitored_service,
        modelled_position_service=modelled_service,
    ).execute()

    reverse = result.hierarchy[0].items[0]
    assert reverse.base_report_value == 20.0
    assert reverse.model_report_value is None
    assert reverse.model_position is None
    assert result.hierarchy[0].model_report_value == 100.0


def test_balance_calculator_uses_parent_modelled_position_with_only_reverse_children():
    monitored_service = MagicMock()
    monitored_service.get_value.return_value = 100.0
    modelled_service = MagicMock()
    modelled_service.resolve_value.return_value = ModelledPositionValue(
        75.0, "contract", "deterministic"
    )
    tree = GlTreeModel(
        name="Balance",
        options=GlTreeOptionsModel(year=2026, report_currency="rub"),
        hierarchy=[
            GlTreeNodeModel(
                name="Parent",
                base_position="parent",
                model_position="contract://parent?mode=deterministic",
                items=[
                    GlTreeNodeModel(name="Reverse 1", direction="REVERSE"),
                    GlTreeNodeModel(name="Reverse 2", direction="REVERSE"),
                ],
            )
        ],
    )

    result = BalanceCalculator(
        tree,
        dt.date(2026, 5, 8),
        scenario="base",
        monitored_position_service=monitored_service,
        modelled_position_service=modelled_service,
    ).execute()

    assert result.hierarchy[0].model_report_value == 75.0
    modelled_service.resolve_value.assert_called_once()


def test_balance_calculator_falls_back_to_monitoring_when_simulation_data_is_missing():
    monitored_service = MagicMock()
    monitored_service.get_value.return_value = 11.0
    modelled_service = MagicMock()
    modelled_service.resolve_value.return_value = ModelledPositionValue(
        None, "contract", "simulation"
    )
    tree = GlTreeModel(
        name="Balance",
        options=GlTreeOptionsModel(year=2026, report_currency="rub"),
        hierarchy=[
            GlTreeNodeModel(
                name="Cash",
                base_position="dataset://MONITORED_DATA?page_title=Assets&entity_name=Entity%20A&metric_name=Cash",
                model_position="contract://?slug=CASH&mode=sim",
            )
        ],
    )

    result = BalanceCalculator(
        tree,
        dt.date(2026, 5, 8),
        scenario="base",
        monitored_position_service=monitored_service,
        modelled_position_service=modelled_service,
    ).execute()

    assert result.base_report_total == 11.0
    assert result.model_report_total == 11.0
    assert result.hierarchy[0].model_report_value == 11.0
    assert result.hierarchy[0].data_source_type == "contract"


def test_balance_calculator_keeps_real_zero_simulation_value():
    monitored_service = MagicMock()
    monitored_service.get_value.return_value = 11.0
    modelled_service = MagicMock()
    modelled_service.resolve_value.return_value = ModelledPositionValue(
        0.0, "contract", "simulation"
    )
    tree = GlTreeModel(
        name="Balance",
        options=GlTreeOptionsModel(year=2026, report_currency="rub"),
        hierarchy=[
            GlTreeNodeModel(
                name="Cash",
                base_position="dataset://MONITORED_DATA?page_title=Assets&entity_name=Entity%20A&metric_name=Cash",
                model_position="contract://?slug=CASH&mode=sim",
            )
        ],
    )

    result = BalanceCalculator(
        tree,
        dt.date(2026, 5, 8),
        scenario="base",
        monitored_position_service=monitored_service,
        modelled_position_service=modelled_service,
    ).execute()

    assert result.base_report_total == 11.0
    assert result.model_report_total == 0.0
    assert result.hierarchy[0].model_report_value == 0.0
    assert result.hierarchy[0].data_source_type == "contract"


def test_balance_calculator_prepares_deterministic_snapshot_once_for_tree_contracts():
    monitored_service = MagicMock()
    modelled_service = MagicMock()
    modelled_service.resolve_value.return_value = ModelledPositionValue(
        1.0, "contract", "deterministic"
    )
    tree = GlTreeModel(
        name="Balance",
        options=GlTreeOptionsModel(year=2026, report_currency="rub"),
        hierarchy=[
            GlTreeNodeModel(
                name="Parent",
                model_position="contract://?slug=contract2&mode=det",
                items=[
                    GlTreeNodeModel(
                        name="Child 1",
                        model_position="contract://?slug=contract1&mode=det",
                    ),
                    GlTreeNodeModel(
                        name="Child 2",
                        model_position="contract://?slug=contract1&mode=det",
                    ),
                    GlTreeNodeModel(
                        name="Simulation Child",
                        model_position="contract://?slug=contract3&mode=sim",
                    ),
                ],
            )
        ],
    )

    BalanceCalculator(
        tree,
        dt.date(2026, 5, 8),
        scenario="base",
        monitored_position_service=monitored_service,
        modelled_position_service=modelled_service,
    ).execute()

    modelled_service.prepare_deterministic_snapshot.assert_not_called()
    modelled_service.resolve_value.assert_called()


def test_calculate_endpoint_accepts_observ_date_and_returns_calculated_tree(tmp_path, monkeypatch):
    import api.valuation.gl_calculated_tree as gl_calculated_tree_module
    import infrastructure.files.filestore_registry as filestore_registry

    balance_root = _prepare_locations(tmp_path, monkeypatch)
    filestore_registry._file_store_registry_instance = None
    _write_csv(
        balance_root / "observ_date=2026-05-07" / "report_year=2026" / "part-001.csv",
        [
            {
                "report_id": "r1",
                "page_title": "Assets",
                "row_index": 1,
                "entity_name": "Entity A",
                "metric_name": "Cash",
                "metric_value": 7,
                "metric_period": "2026-01",
                "loaded_at": "2026-05-07T00:00:00",
            }
        ],
    )
    monkeypatch.setattr(GlTreeRepository, "__init__", lambda self: None)
    monkeypatch.setattr(GlTreeRepository, "get_first", lambda self, slug_or_name: _build_tree())
    monkeypatch.setattr(
        gl_calculated_tree_module,
        "create_gl_tree_command_bus",
        lambda logger_: MagicMock(
            query=lambda request: BalanceCalculator(
                _build_tree(),
                request.observation_date,
                request.scenario,
                _dataset_monitored_service([7]),
                MagicMock(
                    resolve_value=MagicMock(
                        return_value=ModelledPositionValue(None, "none", "deterministic")
                    )
                ),
            ).execute()
        ),
    )

    response = calculate(
        gl_tree_slug="balance",
        observ_date="2026-05-08",
        scenario="base",
        valuation_type="eod",
        modelled_position_reducer="median",
    )

    assert response.base_report_total == 7.0
    assert response.hierarchy[0].base_report_value == 7.0


def test_calculate_endpoint_rejects_invalid_observ_date():
    with pytest.raises(Exception) as exc_info:
        calculate(gl_tree_slug="balance", observ_date="2026/05/08")

    assert "observ_date must be in YYYYMMDD or YYYY-MM-DD format" in str(exc_info.value)
