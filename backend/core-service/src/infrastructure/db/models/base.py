# Базовый класс entity-моделей


from typing import Any, Dict

from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase

DB_SCHEMA = "sol_gtrm"
DEFAULT_TABLE_ARGS = {"schema": f"{DB_SCHEMA}"}


class Base(DeclarativeBase):
    """Базовый класс моделей"""

    __table_args__ = DEFAULT_TABLE_ARGS

    type_annotation_map = {Dict[str, Any]: JSONB}
