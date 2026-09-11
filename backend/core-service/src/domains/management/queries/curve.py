import datetime
from typing import Dict, List

from shared.cqrs.query import QueryHandler


class GetCurvePointsQueryHandler(QueryHandler[CurvePointsQuery, List[Dict]]):
    """Запрос на получение точек кривой"""

    def execute(self, query: CurvePointsQuery) -> List[Dict]:
	pass
