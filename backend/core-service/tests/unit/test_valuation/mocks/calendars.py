import datetime

import numpy as np

from domains.risk.repositories.calendar_data import CalendarDataObjects


class CalendarDataObjectsMock(CalendarDataObjects):

    def __init__(self):
        self._business_days_cache = {}     
        start_date = datetime.date(2024, 1, 1)
        dates = [(start_date + datetime.timedelta(x)) for x in range(600)]
        cached = np.array([x.toordinal() for x in dates if x.weekday() < 5])
        self._business_days_cache["default"] = cached   
        self._business_days_cache["default_uk"] = cached                

    def _get_business_dates(self, name_or_slug: str) -> np.ndarray:   
        return self._business_days_cache[name_or_slug]
    

 

