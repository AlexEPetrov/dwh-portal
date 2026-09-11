import datetime
import uuid
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from domains.common.models.mixins import VersionedModelMixin


class AppBaseModel(BaseModel):
    id: Optional[uuid.UUID] = Field(
        default=None,
        json_schema_extra={
            "ui:hidden": True,
        },
    )
    """Идентификатор объекта"""

    model_config = ConfigDict(use_attribute_docstrings=True)


class NamedObjectModel(AppBaseModel):
    name: str = Field(
        str,
        json_schema_extra={
            "ui:property_priority": 1,
        },
    )
    """Наименование объекта"""
    slug: Optional[str] = Field(
        default=None,
        json_schema_extra={
            "ui:property_priority": 2,
        },
    )
    """Системное имя или код объекта (только английский)"""
    description: Optional[str] = Field(
        default=None,
        json_schema_extra={
            "ui:property_priority": 3,
        },
    )
    """Описание объекта"""

    def get_slug_or_name(self):
        return self.slug if self.slug is not None else self.name


class VersionedObjectModel(AppBaseModel, VersionedModelMixin):
    pass


class ScenarioConfigurableObjectModel(AppBaseModel):
    scenario: Optional[str] = None
    """Сценарий. Для дополнительного сценария можно определить настраиваемые объемы поставки или
    параметры ценообразования.
    Удаление соответствующего свойства приведет к использованию параметров базового сценария."""


class CategorizedObjectModel(AppBaseModel):
    category: Optional[str] = Field(
        default=None,
        json_schema_extra={
            "ui:property_priority": 4,
        },
    )
    """Дополнительная категоризация контракта или другого объекта. Обычно имеет смысл выделять категории
    по типу продукта (Gas, oil..), стране, поставщику/покупателю или или источнику даных (Argus/TTF/spot).
    При импорте в Excel - создаются worksheets по именам категорий."""


class TaggedObjectModel(AppBaseModel):
    tag: Optional[str] = Field(
        default=None,
        description="Набор строковых идентификаторов (тегов), разделенных пробелом, например TTF GAS ARGUS",
        json_schema_extra={
            "ui:property_priority": 5,
        },
    )
    """Набор строковых идентификаторов (тегов), разделенных пробелом, например TTF GAS ARGUS"""


class LoggedObjectModel(AppBaseModel):
    created_at: Optional[datetime.datetime] = None
    modified_at: Optional[datetime.datetime] = None


class ActivatableObjectModel(AppBaseModel):
    is_active: bool = Field(
        default=True,
        json_schema_extra={
            "ui:group": {"name": "Версия", "priority": 100},
            "ui:property_priority": 6,  # Порядок внутри группы
        },
    )
    """Является ли объект активным (актуальным, к расчету или к использованию)"""


class ObjectInfoModel(NamedObjectModel, VersionedObjectModel, LoggedObjectModel):
    "Типовые свойства объектов для загрузки списка моделей"
