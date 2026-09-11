import datetime
from typing import Any, List

from domains.risk.models.curve import CurveDefinition, CurvePoint
from domains.risk.models.scenario import Scenario
from domains.risk.repositories.curve_data import CurveDataObjects


class CurveDataObjectsMock(CurveDataObjects):

    def __init__(self, session=None, auto_commit=True):
        # super().__init__(session, auto_commit)
        self.curve_points = {}

    def get_effective_curve_points(
        self,
        model: CurveDefinition,
        scenario: Scenario,
        observation_date: datetime.date,
        min_date: datetime.date,
        max_date: datetime.date,
        forecast_mode: bool,
    ) -> List[Any]:
        curve_values: List[CurvePoint] = self.curve_points.get(model.get_slug_or_name())
        if not curve_values:
            return []

        return filter(
            lambda x: x.report_date >= min_date and x.report_date <= max_date, curve_values
        )

    def update(self, model, entity_find_func=None):
        self.curve_points[model.curve.name] = model.values
