"""вспомогательные методы для работы с Pydantic"""

from enum import Enum
from typing import List
from pydantic import BaseModel

import sys 

if sys.version_info[:3] > (3, 10):
    from enum import StrEnum
else:
    from strenum import StrEnum


def enumerate_primitive_fields(model: BaseModel, exclude: List[str] = []):
    primitive_types = (int, float, str, bool)  # Define primitive types
    primitive_fields = []

    for field_name, field_info in model.model_fields.items():
        field_annotation = field_info.annotation

        if hasattr(field_annotation, '__args__'):
            underlying_type = field_annotation.__args__[0]
        else:
            underlying_type = field_annotation

        # Check if the field is a primitive type
        if underlying_type in primitive_types:
            primitive_fields.append(field_name)
        # Check if the field is an Enum
        elif isinstance(underlying_type, type) and issubclass(underlying_type, StrEnum):
            primitive_fields.append(field_name)
        elif isinstance(underlying_type, type) and issubclass(underlying_type, Enum):
            primitive_fields.append(field_name)

    return [x for x in primitive_fields if x not in exclude]