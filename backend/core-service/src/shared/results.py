import logging
from dataclasses import dataclass, field
from enum import StrEnum  # Python 3.11+, или свой велосипед
from typing import Any, Generic, Optional, TypeVar, Union

from shared.nullables import require

T = TypeVar("T")  # TODO - перейти на "T", default=Any при переходе на 3.13+


@dataclass
class ServiceNotification:
    """Уведомление с поддержкой StrEnum"""

    code: Union[str, StrEnum]  # StrEnum автоматически работает как str
    message_template: str
    context: dict = field(default_factory=dict)

    def format_message(self) -> str:
        try:
            return self.message_template.format(**self.context)
        except KeyError:
            return self.message_template

    @property
    def code_str(self) -> str:
        """Всегда возвращает строку (StrEnum и так строка, но для единообразия)"""
        return str(self.code)  # StrEnum конвертится в строку автоматически


@dataclass
class ServiceResult(Generic[T]):
    data: Optional[T] = None
    _errors: list[ServiceNotification] = field(default_factory=list)
    _warnings: list[ServiceNotification] = field(default_factory=list)
    _infos: list[ServiceNotification] = field(default_factory=list)

    @property
    def is_success(self) -> bool:
        return len(self._errors) == 0

    def add_error(
        self, code: Union[str, StrEnum], message_template: str, **context
    ) -> "ServiceResult[T]":
        logging.getLogger().error(message_template, extra=context)
        self._errors.append(ServiceNotification(code, message_template, context))
        return self

    def add_warning(
        self, code: Union[str, StrEnum], message_template: str, **context
    ) -> "ServiceResult[T]":
        logging.getLogger().warning(message_template, extra=context)
        self._warnings.append(ServiceNotification(code, message_template, context))
        return self

    def add_info(
        self, code: Union[str, StrEnum], message_template: str, **context
    ) -> "ServiceResult[T]":
        logging.getLogger().info(message_template, extra=context)
        self._infos.append(ServiceNotification(code, message_template, context))
        return self

    @classmethod
    def fail(
        cls, code: Union[str, StrEnum], message_template: str, **context
    ) -> "ServiceResult[T]":
        result = cls()
        result.add_error(code, message_template, **context)
        return result

    def to_dict(self, human_readable: bool = True) -> dict:
        result = {}

        if self.data is not None:
            result["data"] = self.data

        if self._errors:
            if human_readable:
                result["errors"] = [n.format_message() for n in self._errors]
            else:
                result["errors"] = [
                    {"code": n.code_str, "message": n.format_message(), "context": n.context}
                    for n in self._errors
                ]

        if self._warnings:
            if human_readable:
                result["warnings"] = [n.format_message() for n in self._warnings]
            else:
                result["warnings"] = [
                    {"code": n.code_str, "message": n.format_message(), "context": n.context}
                    for n in self._warnings
                ]

        return result


@dataclass
class SimpleServiceResult(ServiceResult[Any]):

    @classmethod
    def warning(
        cls, code: Union[str, StrEnum], message_template: str, **context
    ) -> "SimpleServiceResult":
        """Создает успешный результат с одним предупреждением"""
        result = SimpleServiceResult()
        result.add_warning(code, message_template, **context)
        return result

    @classmethod
    def ok(cls, data: Any = None) -> "SimpleServiceResult":
        """Переопределяем, чтобы data всегда был списком"""
        return cls(data)


@dataclass
class CombinedServiceResult(ServiceResult[list]):
    """Результат для сбора коллекции данных"""

    def __post_init__(self):
        """Гарантируем, что data всегда список"""
        if self.data is None:
            self.data = []
        elif not isinstance(self.data, list):
            self.data = [self.data]

    def add(self, other: ServiceResult) -> "CombinedServiceResult":
        """Добавляет результат из любого ServiceResult"""
        # Добавляем данные
        if other.data is not None:
            if isinstance(other.data, list):
                require(self.data).extend(other.data)
            else:
                require(self.data).append(other.data)

        # Добавляем уведомления
        self._errors.extend(other._errors)
        self._warnings.extend(other._warnings)
        self._infos.extend(other._infos)

        return self

    def __iadd__(self, other: ServiceResult) -> "CombinedServiceResult":
        """Поддержка += синтаксиса"""
        return self.add(other)

    @classmethod
    def ok(cls, data: list | None = None) -> "CombinedServiceResult":
        """Переопределяем, чтобы data всегда был списком"""
        return cls(data=data or [])
