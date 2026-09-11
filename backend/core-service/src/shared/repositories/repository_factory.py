from typing import Type, TypeVar

from shared.repositories.generic_repository import GenericRepository

TModel = TypeVar("TModel")
TRepository = TypeVar("TRepository")


class RepositoryFactory:
    """Фабрика репо. Использование:
    - Зарегистрировать типы репозиториев через register(model_type, repo_type)
    - Получить инстанс через create_repository
    """

    def __init__(self):
        self._registered_type_mappings = {}

    def register(self, cls: Type[TModel], cls_repository: Type[TRepository]):
        self._registered_type_mappings[cls] = cls_repository

    def create_repository(self, cls: Type[TModel], *args, **kwargs) -> GenericRepository[TModel]:

        repo_type = self._registered_type_mappings.get(cls)
        if not repo_type:
            raise NotImplementedError()

        ret_val = repo_type(*args, **kwargs)

        return ret_val
