from typing import Optional

from pydantic import BaseModel, Field


class VersionedModelMixin(BaseModel):
    """Здесь, а не в домене, чтобы можно было использовать версионирование в разных доменах
    при необходимости с поддержкой в Generic-реализациях репозиториев"""

    version: int = Field(
        default=1,
        json_schema_extra={
            "ui:group": {"name": "Версия", "priority": 100},
            "ui:property_priority": 1,  # Порядок внутри группы
        },
    )
    """Текущая версия объекта. Изменяется (+1) автоматически при сохранении."""
    version_description: Optional[str] = Field(
        default=None,
        json_schema_extra={
            "ui:group": {"name": "Версия", "priority": 100},
            "ui:property_priority": 2,  # Порядок внутри группы
        },
    )
    """Описание изменений (опционально)"""
    author: Optional[str] = Field(
        default=None,
        json_schema_extra={
            "ui:group": {"name": "Версия", "priority": 100},
            "ui:property_priority": 3,  # Порядок внутри группы
        },
    )
    "Автор изменений (опционально)"
