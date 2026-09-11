from abc import ABC, abstractmethod
from typing import Type, TypeVar

from shared.repositories.generic_repository import GenericRepository


TModel = TypeVar("TModel")

class RepositoryRegistryBase(ABC):
    """Базовый класс для реестра репозиториев. 
    Реестр - это кэш репозиториев, который может создавать их через фабрику/кеш при необходимости.
    """

    @abstractmethod
    def get_repository(self, model_type: Type[TModel]) -> GenericRepository[TModel]:
        raise NotImplementedError()