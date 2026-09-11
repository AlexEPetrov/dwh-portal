from abc import ABC, abstractmethod
from typing import Any, Generator, Generic, Optional, Tuple, TypeVar

TModel = TypeVar("TModel")


class GenericRepository(Generic[TModel], ABC):
    """Базовый класс generic-репозитория"""

    @abstractmethod
    def get_all(self) -> Generator[TModel, None, None]:
        raise NotImplementedError()

    @abstractmethod
    def update(self, model: TModel) -> Tuple[TModel, Any]:
        raise NotImplementedError()

    @abstractmethod
    def delete(self, slug: str) -> None:
        raise NotImplementedError()

    @abstractmethod
    def get_first(self, slug_or_name: str, scenario: str | None = None) -> Optional[TModel]:
        raise NotImplementedError()
