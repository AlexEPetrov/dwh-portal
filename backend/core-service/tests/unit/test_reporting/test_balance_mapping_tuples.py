import datetime as dt

import pytest

from api.reporting.balance_mapping import get_balance_mapping_tuples
from domains.reporting.services.balance_mapping import BalanceMappingTupleService

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
    monkeypatch.setenv("APP_LOC_VALUATION_TARGET_PATH", "")
    monkeypatch.setenv("APP_LOC_VALUATION_TARGET_ROOT", str(tmp_path / "valuation_target"))
    monkeypatch.setenv("APP_LOC_TEMP_PATH", str(tmp_path / "tmp"))
    monkeypatch.setenv("APP_LOC_BALANCE_DATA_ROOT", str(tmp_path / "balance_data"))
    return tmp_path / "balance_data"


def _write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open(mode="w", encoding="utf-8", newline="") as file_obj:
        file_obj.write(CSV_HEADER)
        for row in rows:
            file_obj.write(
                "{report_id},{page_title},{subheader},{row_index},{entity_name},{metric_name},{metric_value},{metric_period},{loaded_at}\n".format(
                    **row
                )
            )


def test_balance_mapping_tuple_service_returns_distinct_tuples_from_nearest_partition(
    tmp_path, monkeypatch
):
    balance_root = _prepare_locations(tmp_path, monkeypatch)

    _write_csv(
        balance_root / "report_date=20260507" / "report_year=2026" / "part-001.csv",
        [
            {
                "report_id": "r1",
                "page_title": "Assets",
                "subheader": "Current assets",
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
                "subheader": "Current assets",
                "row_index": 2,
                "entity_name": "Entity A",
                "metric_name": "Cash",
                "metric_value": 2,
                "metric_period": "2026-02",
                "loaded_at": "2026-05-07T00:00:00",
            },
            {
                "report_id": "r3",
                "page_title": "Liabilities",
                "subheader": "Long-term",
                "row_index": 3,
                "entity_name": "Entity B",
                "metric_name": "Debt",
                "metric_value": 3,
                "metric_period": "2026-01",
                "loaded_at": "2026-05-07T00:00:00",
            },
            {
                "report_id": "r4",
                "page_title": "",
                "subheader": "Ignored",
                "row_index": 4,
                "entity_name": "Entity B",
                "metric_name": "Ignored",
                "metric_value": 4,
                "metric_period": "2026-01",
                "loaded_at": "2026-05-07T00:00:00",
            },
        ],
    )
    _write_csv(
        balance_root / "report_date=20260507" / "report_year=2027" / "part-002.csv",
        [
            {
                "report_id": "r5",
                "page_title": "Revenue",
                "subheader": "Sales performance",
                "row_index": 1,
                "entity_name": "Entity C",
                "metric_name": "Sales",
                "metric_value": 5,
                "metric_period": "2027-01",
                "loaded_at": "2026-05-07T00:00:00",
            }
        ],
    )
    _write_csv(
        balance_root / "report_date=20260428" / "report_year=2026" / "part-003.csv",
        [
            {
                "report_id": "r6",
                "page_title": "Old Assets",
                "subheader": "Archive",
                "row_index": 1,
                "entity_name": "Entity Z",
                "metric_name": "Legacy",
                "metric_value": 6,
                "metric_period": "2026-01",
                "loaded_at": "2026-04-28T00:00:00",
            }
        ],
    )

    catalog = BalanceMappingTupleService().get_catalog(dt.date(2026, 5, 1))

    assert catalog.report_date == dt.date(2026, 4, 28)
    assert [
        (item.page_title, item.subheader, item.entity_name, item.metric_name)
        for item in catalog.tuples
    ] == [
        ("Old Assets", "Archive", "Entity Z", "Legacy"),
    ]
    assert catalog.tuples[0].serialized_value() == '["Old Assets","Archive","Entity Z","Legacy"]'


def test_balance_mapping_tuple_service_raises_when_partition_is_missing(tmp_path, monkeypatch):
    _prepare_locations(tmp_path, monkeypatch)

    with pytest.raises(LookupError):
        BalanceMappingTupleService().get_catalog(dt.date(2026, 4, 1))


def test_get_balance_mapping_tuples_endpoint_returns_frontend_ready_payload(tmp_path, monkeypatch):
    balance_root = _prepare_locations(tmp_path, monkeypatch)
    _write_csv(
        balance_root / "report_date=20260507" / "report_year=2026" / "part-001.csv",
        [
            {
                "report_id": "r1",
                "page_title": "Assets",
                "subheader": "Current assets",
                "row_index": 1,
                "entity_name": "Entity A",
                "metric_name": "Cash",
                "metric_value": 1,
                "metric_period": "2026-01",
                "loaded_at": "2026-05-07T00:00:00",
            }
        ],
    )

    response = get_balance_mapping_tuples("2026-05-08")

    assert response.observ_date == "20260508"
    assert response.report_date == "20260507"
    assert response.tuples[0].label == "Assets / Current assets / Entity A / Cash"
    assert response.tuples[0].value == '["Assets","Current assets","Entity A","Cash"]'


def test_balance_mapping_tuple_service_returns_source_rows_for_explicit_report_date(
    tmp_path, monkeypatch
):
    balance_root = _prepare_locations(tmp_path, monkeypatch)
    _write_csv(
        balance_root / "report_date=20260507" / "report_year=2026" / "part-001.csv",
        [
            {
                "report_id": "r1",
                "page_title": "Assets",
                "subheader": "Current assets",
                "row_index": 1,
                "entity_name": "Entity A",
                "metric_name": "Cash",
                "metric_value": 100,
                "metric_period": "2026-01",
                "loaded_at": "2026-05-07T00:00:00",
            },
            {
                "report_id": "r2",
                "page_title": "",
                "subheader": "Debt bucket",
                "row_index": 2,
                "entity_name": "Entity B",
                "metric_name": "Debt",
                "metric_value": 200,
                "metric_period": "2026-02",
                "loaded_at": "2026-05-07T00:00:00",
            },
        ],
    )

    document = BalanceMappingTupleService().get_source_document(report_date=dt.date(2026, 5, 7))

    assert document.observation_date is None
    assert document.report_date == dt.date(2026, 5, 7)
    assert [
        (row.page_title, row.subheader, row.entity_name, row.metric_name, row.metric_value)
        for row in document.rows
    ] == [
        ("", "Debt bucket", "Entity B", "Debt", "200"),
        ("Assets", "Current assets", "Entity A", "Cash", "100"),
    ]
    assert document.rows[0].tuple_value() is None
    assert document.rows[1].tuple_value() == '["Assets","Current assets","Entity A","Cash"]'


def test_get_monitoring_source_document_endpoint_returns_rows_and_report_dates(
    tmp_path, monkeypatch
):
    from api.reporting.balance_mapping import (
        get_monitoring_report_dates,
        get_monitoring_source_document,
    )

    balance_root = _prepare_locations(tmp_path, monkeypatch)
    _write_csv(
        balance_root / "report_date=20260507" / "report_year=2026" / "part-001.csv",
        [
            {
                "report_id": "r1",
                "page_title": "Assets",
                "subheader": "Current assets",
                "row_index": 1,
                "entity_name": "Entity A",
                "metric_name": "Cash",
                "metric_value": 100,
                "metric_period": "2026-01",
                "loaded_at": "2026-05-07T00:00:00",
            }
        ],
    )
    _write_csv(
        balance_root / "report_date=20260428" / "report_year=2026" / "part-002.csv",
        [
            {
                "report_id": "r2",
                "page_title": "Legacy",
                "subheader": "Archive",
                "row_index": 1,
                "entity_name": "Entity Z",
                "metric_name": "Carry",
                "metric_value": 50,
                "metric_period": "2026-01",
                "loaded_at": "2026-04-28T00:00:00",
            }
        ],
    )

    report_dates_response = get_monitoring_report_dates()
    source_response = get_monitoring_source_document(observ_date="2026-05-08")

    assert report_dates_response.report_dates == ["20260428", "20260507"]
    assert source_response.observ_date == "20260508"
    assert source_response.report_date == "20260507"
    assert source_response.rows[0].subheader == "Current assets"
    assert source_response.rows[0].label == "Assets / Current assets / Entity A / Cash"
    assert source_response.rows[0].value == '["Assets","Current assets","Entity A","Cash"]'
    assert source_response.rows[0].metric_value == "100"
