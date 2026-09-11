import logging
from abc import ABC, abstractmethod
from typing import Any, Generic, TypeVar

from pydantic import BaseModel

TResult = TypeVar("TResult")


class QueryBase(BaseModel, Generic[TResult]):
    """Базовый класс для реализации запросов (CQRS)"""


TQuery = TypeVar("TQuery", bound=QueryBase[Any])


class QueryHandler(Generic[TQuery, TResult], ABC):
    """Базовый класс для реализации обработчика команды"""

    def __init__(self, logger):
        super().__init__()
        self.logger: logging.Logger = logger

    @abstractmethod
    def execute(self, query: TQuery) -> TResult: ...
