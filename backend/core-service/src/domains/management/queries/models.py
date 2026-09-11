import datetime
from typing import Dict, List, Optional

from pydantic import model_validator

from shared.cqrs.query import QueryBase


class CurvePointsQuery(QueryBase[List[Dict]]):
    """Запрос данных по кривой в заданном диапазоне дат и точки наблюдения"""

    observation_date: datetime.date
    curve: str
    min_date: datetime.date
    max_date: datetime.date
    scenario: Optional[str]
    allow_forecast: bool = True

    @model_validator(mode="after")
    def _check_time_range(self):
        if self.min_date > self.max_date:
            raise ValueError("Некорректный диапазон дат")
        return self
