# import datetime
# from typing import Any, List

# import numpy as np

# import pytest

# from domains.risk.models.curve import CurveDefinition
# from domains.risk.models.scenario import Scenario
# from domains.risk.repositories.calendar_data import CalendarDataObjects
# from domains.risk.repositories.curve_data import CurveDataObjects


# class CalendarDataObjectsMock(CalendarDataObjects):

#     def __init__(self):
#         self._business_days_cache = {}     
#         start_date = datetime.date(2024, 1, 1)
#         dates = [(start_date + datetime.timedelta(x)) for x in range(600)]
#         cached = np.array([x.toordinal() for x in dates if x.weekday() < 5])
#         self._business_days_cache["default"] = cached        

#     def _get_business_dates(self, name_or_slug: str) -> np.ndarray:   
#         return self._business_days_cache[name_or_slug]
    

# class CurveDataObjectsMock(CurveDataObjects):

#     def __init__(self, session = None, auto_commit = True):
#         super().__init__(session, auto_commit)

#     def get_effective_curve_points(
#         self,
#         model: CurveDefinition,
#         scenario: Scenario,
#         observation_date: datetime.date,
#         min_date: datetime.date,
#         max_date: datetime.date,
#         forecast_mode: bool
#     ) -> List[Any]:    
#         return []    

# @pytest.fixture
# def calendars():
#     return CalendarDataObjectsMock()    


# @pytest.fixture
# def curves():
#     return CurveDataObjectsMock()    