"""Cоздание иерархической структуры нативных датаклассов из json.
используется при десереализации json напрямую в классы моделей (pydantic здесь не используется!).
Сгенерированно DS, вручную поддержка Literals"""
import sys 
from dataclasses import is_dataclass, fields
from typing import Any, Type, TypeVar, get_origin, get_args, Literal, Union

if sys.version_info[:3] < (3, 9):
    from typing_extensions import get_type_hints
else:
    from typing import get_type_hints

import json
from datetime import datetime, date
from decimal import Decimal
from enum import Enum
from uuid import UUID

T = TypeVar('T')

def from_json(cls: Type[T], data: Any, type_mappings) -> T:
    """Convert JSON data to a dataclass instance with proper type handling"""
    if isinstance(data, str):
        data = json.loads(data)
    
    if not is_dataclass(cls):
        raise ValueError(f"Expected dataclass type, got {cls}")
    
    kwargs = {}
    type_hints = get_type_hints(cls, include_extras=True)

    # do we have discriminator field for this class?
    # if yes then use it instead of cls.
    if isinstance(data, dict):
        type_value = data.get("type")
        if type_value:
            cls = type_mappings[type_value]

    
    for field in fields(cls):
        field_name = field.name
        if field_name not in data:
            if field.default is not field.default_factory:
                kwargs[field_name] = field.default
            continue
            
        value = data[field_name]
        field_type = type_hints[field_name]
        
        kwargs[field_name] = _validate_value(field_type, value, type_mappings, field_name)
    
    return cls(**kwargs)

def _validate_value(field_type: Type, value: Any, type_mappings, field_name: str) -> Any:
    """Validate and convert a value according to the field's type annotation"""
    # Handle None values for Optional types
    if value is None:
        if _is_optional(field_type):
            return None
        raise ValueError(f"Field '{field_name}' cannot be None")
    
    if str(field_type).startswith("typing.Annotated") or str(field_type).startswith("typing_extensions.Annotated"):
        field_type = get_args(field_type)[0]
    
    # Handle Optional[UUID] specifically
    if _is_optional_uuid(field_type):
        try:
            return UUID(str(value)) if value is not None else None
        except (ValueError, AttributeError) as e:
            raise ValueError(f"Invalid UUID format for field '{field_name}': {value}") from e
    
    # Handle UUID type (non-optional)
    if field_type is UUID:
        try:
            return UUID(str(value))
        except (ValueError, AttributeError) as e:
            raise ValueError(f"Invalid UUID format for field '{field_name}': {value}") from e
    
    # Handle Optional types (generic)
    if _is_optional(field_type):
        inner_type = get_args(field_type)[0]
        return _validate_value(inner_type, value, type_mappings, field_name)
    
    # Handle Union types (excluding Optional)
    if _is_union(field_type):
        for subtype in get_args(field_type):
            if subtype is type(None):
                continue
            try:
                return _validate_value(subtype, value, type_mappings, field_name)
            except ValueError as ex:
                continue
        raise ValueError(f"Value '{value}' doesn't match any type in Union for field '{field_name}'")
    
    # Handle Literal types
    if _is_literal(field_type):
        allowed_values = get_args(field_type)
        if value not in allowed_values:
            raise ValueError(
                f"Value '{value}' for field '{field_name}' is not in allowed values: {allowed_values}"
            )
        return value
    
    # Handle nested dataclasses
    if is_dataclass(field_type):
        return from_json(field_type, value, type_mappings)
    
    # Handle lists
    if get_origin(field_type) is list:
        # и обрабатываем разные типы
        ret_val = []
        for index, item in enumerate(value):
            item_type = get_args(field_type)[0]
            item_to_add = _validate_value(item_type, item, type_mappings, field_name)
            ret_val.append(item_to_add)
        return ret_val
    
    # Handle special types
    if field_type is datetime:
        return datetime.fromisoformat(value)
    if field_type is date:
        return date.fromisoformat(value)
    if field_type is Decimal:
        return Decimal(str(value))
    if isinstance(field_type, type) and issubclass(field_type, Enum):
        return field_type(value)
    
    # Handle simple type conversion
    try:
        return field_type(value)
    except (TypeError, ValueError) as e:
        raise ValueError(
            f"Failed to convert field '{field_name}' with value '{value}' to type {field_type}"
        ) from e

def _is_optional(field_type: Type) -> bool:
    """Check if a type is Optional[T]"""
    return get_origin(field_type) is Union and type(None) in get_args(field_type)

def _is_optional_uuid(field_type: Type) -> bool:
    """Check if a type is Optional[UUID]"""
    if get_origin(field_type) is Union:
        args = get_args(field_type)
        return len(args) == 2 and type(None) in args and UUID in args
    return False

def _is_union(field_type: Type) -> bool:
    """Check if a type is a Union (not including Optional)"""
    origin = get_origin(field_type)
    return origin is Union and not (len(get_args(field_type)) == 2 and type(None) in get_args(field_type))

def _is_literal(field_type: Type) -> bool:
    """Check if a type is a Literal type"""
    return get_origin(field_type) is Literal