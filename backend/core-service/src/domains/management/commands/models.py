import datetime as dt
from typing import List, Optional

from shared.cqrs.core import Command


class LoadCurvesCommand(Command):
    """Команда загрузки кривых на дату"""

    date: dt.date
    curves_pattern: Optional[str] = None
    curves: Optional[List[str]] = None


