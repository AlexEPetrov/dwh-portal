import csv
import io
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List
from uuid import UUID

from attr import dataclass
from fastapi.responses import PlainTextResponse


class RequestStatus(Enum):
    UNKNOWN = 0
    REQUESTED = 1
    COMPLETED = 2
    ERROR = 3
    RUNNING = 4


@dataclass
class RequestContext:
    request_time: datetime
    request_id: UUID
    status: RequestStatus = RequestStatus.UNKNOWN
    message: str = ""
    token: Any = None


def dicts_to_csv(values: List[Dict[Any, Any]]):
    """Генерация ответа с CSV body для публикации через WebAPI"""

    if not values:
        return PlainTextResponse("")

    fieldnames = values[0].keys()

    csv_in_memory = io.StringIO(newline="")
    writer = csv.DictWriter(csv_in_memory, fieldnames=fieldnames, quoting=csv.QUOTE_NONNUMERIC)

    writer.writeheader()
    writer.writerows(values)

    return PlainTextResponse(csv_in_memory.getvalue())
