import datetime as dt
from types import SimpleNamespace

from domains.risk.models.curve import CurvePointIntervalEnum
from proto.simulation_streamer import CurveBlockReader, StreamTuning


def _curve(point_interval: CurvePointIntervalEnum):
    return SimpleNamespace(name="CURVE", point_interval=point_interval)


def _reader(observation_date: dt.date) -> CurveBlockReader:
    return CurveBlockReader(
        parquet_files={},
        curves=[],
        observation_date=observation_date,
        tuning=StreamTuning(),
        logger=SimpleNamespace(),
    )


def test_daily_simulation_stream_starts_after_observation_date():
    reader = _reader(dt.date(2026, 7, 9))

    assert reader._simulation_start_date(_curve(CurvePointIntervalEnum.BIZDAY)) == dt.date(
        2026, 7, 10
    )
    assert reader._simulation_start_date(_curve(CurvePointIntervalEnum.CALDAY)) == dt.date(
        2026, 7, 10
    )


def test_monthly_simulation_stream_starts_at_observation_month_start():
    reader = _reader(dt.date(2026, 7, 9))

    assert reader._simulation_start_date(_curve(CurvePointIntervalEnum.MONTH)) == dt.date(
        2026, 7, 1
    )


def test_quarterly_simulation_stream_starts_at_observation_quarter_start():
    reader = _reader(dt.date(2026, 7, 9))

    assert reader._simulation_start_date(_curve(CurvePointIntervalEnum.QUARTER)) == dt.date(
        2026, 7, 1
    )
