from typing import Annotated, Any, Optional

from pydantic import BaseModel, GetCoreSchemaHandler, field_validator
from pydantic_core import core_schema

from shared.nullables import require
from shared.repositories.generic_registry import RepositoryRegistryBase

# Module-level registry to avoid Pydantic private attribute issues
_repository_registry: RepositoryRegistryBase | None = None


class LookupResolveMixin(BaseModel):
    """
    Миксин для всех lookup-полей:
    - При десериализации name → slug
    - JSON/dict остаётся slug
    """

    @classmethod
    def set_repository_registry(cls, repo_registry: RepositoryRegistryBase):
        global _repository_registry
        _repository_registry = repo_registry

    @field_validator("*", mode="before")
    @classmethod
    def resolve_lookups(cls, v, info):
        """
        Конвертирует name → slug, если поле lookup
        """
        field = cls.model_fields.get(info.field_name)
        if not field or v is None:
            return v

        # ищем lookup-класс
        lookup_type = next((m for m in field.metadata if isinstance(m, LookupType)), None)
        if lookup_type is None:
            return v

        repos = require(_repository_registry)

        # используем репозиторий из фабрики
        repo = repos.get_repository(lookup_type.model_cls)
        if hasattr(repo, "get_first"):
            obj = repo.get_first(v)
            if obj:
                return getattr(obj, "slug", v) or v  # сохраняем slug в модели

        return v

    def export_lookup(self, field_name: str) -> str | None:
        """
        Возвращает значение для UI/Excel (обычно name)
        """
        field = self.model_fields.get(field_name)
        if not field:
            raise ValueError(f"Field {field_name} not found")

        lookup_meta = next((m for m in field.metadata if isinstance(m, LookupType)), None)
        if not lookup_meta:
            # не lookup-поле, просто возвращаем текущее значение
            return getattr(self, field_name, None)

        repos = require(_repository_registry)

        lookup_model = lookup_meta.model_cls
        repo = repos.get_repository(lookup_model)

        slug_value = getattr(self, field_name, None)
        if slug_value is None:
            return None

        # Находим объект по slug и возвращаем name
        if hasattr(repo, "get_first"):
            obj = repo.get_first(slug_value)
            if obj and hasattr(obj, "name"):
                return obj.name

        # fallback — возвращаем текущее значение (slug)
        return slug_value


class LookupType:
    """Метаданные для lookup-поля"""

    def __init__(self, model_cls):
        self.model_cls = model_cls


class LookupStr(str):
    """Строковый тип для lookup-поля"""

    @classmethod
    def __get_pydantic_core_schema__(cls, source, handler: GetCoreSchemaHandler):
        # Обрабатываем как обычную строку. Для совместимости с FastApi
        return core_schema.str_schema()


# class LookupField:
#     """
#     Используется в модели:
#         delivery_market: LookupField[DeliveryMarketModel] = None
#     """

#     def __class_getitem__(cls, model_cls):
#         return Annotated[Optional[LookupStr | str], LookupType(model_cls)]


# 2. Создаем фабрику, которая возвращает ТИП, а не класс
class LookupFieldFactory:
    def __getitem__(self, model_cls: Any) -> Any:
        # Для PyLance это будет выглядеть как Optional[str]
        # Для Pydantic это будет Annotated с метаданными
        return Annotated[Optional[str], LookupType(model_cls)]


# 3. Создаем экземпляр фабрики для использования в аннотациях
LookupField = LookupFieldFactory()
