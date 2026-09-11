"""Модуль, реализующий базовые классы и инфраструктуру для паттерна command bus в рамках CQRS.
Включает в себя базовые классы для команд, контекста выполнения, обработчиков команд, самого command bus и структуры для
результатов выполнения команд. Этот модуль служит основой для построения более сложных бизнес-операций,
которые могут быть разбиты на последовательность команд с общим контекстом выполнения.
"""

# TODO: поддержать вызов enqueue(stop_chain_on_task_failure=True/False). По сути аналог try/finally но в workflow стиле

import logging
import uuid
from abc import ABC
from dataclasses import dataclass, field, replace
from typing import (
    Annotated,
    Any,
    Callable,
    Dict,
    Generic,
    List,
    Optional,
    Type,
    TypeVar,
    Union,
    cast,
)

from pydantic import BaseModel, Field
from pydantic.json_schema import SkipJsonSchema

from api.common import RequestStatus
from shared.cqrs.exceptions import MissingCommandResultError
from shared.cqrs.ports import JobScheduler
from shared.cqrs.query import QueryBase, QueryHandler
from shared.request_manager import RequestManager, get_request_id
from shared.results import ServiceResult


def request_id_default() -> uuid.UUID:
    value = get_request_id()
    if value:
        return uuid.UUID(value)
    return RequestManager.create_request_context().request_id


RequestIdField = Annotated[
    SkipJsonSchema[uuid.UUID],
    Field(default_factory=request_id_default),
]


class Command(BaseModel):
    """Базовый класс для реализации команды (параметры) в рамках command bus pattern (command + command handler)"""

    request_id: RequestIdField
    """Уникальный ID запроса на выполнение команды, полученного от клиента"""


TCommand = TypeVar("TCommand", bound=Command)
TResult = TypeVar("TResult")


class ResultKey:
    pass


RESULT = ResultKey()


@dataclass
class CommandContext:
    """Контект выполнения команд в цепочке команд, выполняемых в command bus. См. примеры использования метода
    update для генерации обновленного контекста, который создается и возвращается после выполнения каждой
    последующей команды"""

    data: Dict[Any, Any]  # command results
    bus: "CommandBus"

    def updated(self, **new_data) -> "CommandContext":
        """Создание нового контекста с обновленными данными (иммутабельность)"""
        return replace(self, bus=self.bus, data={**self.data, **new_data})

    def require(self, key: Any) -> Any:
        """Удобный метод для получения данных из контекста с проверкой наличия ключа"""
        if key not in self.data:
            raise MissingCommandResultError(
                f"Required key '{key}' not found in CommandContext data"
            )
        return self.data[key]


class CommandHandler(Generic[TCommand], ABC):
    """Базовый класс реализации обработчика команд"""

    def __init__(self, logger):
        super().__init__()
        self.logger: logging.Logger = logger

    def execute(
        self, command: TCommand, command_context: CommandContext
    ) -> Union[CommandContext, "CommandResult"]:
        raise NotImplementedError()


class CommandBus:
    """Простейшая реализация конвейера для выполнения команд и запросов - часть CQRS/command bus pattern. Детали
    реализации могут быть расширены в зависимости от потребностей (например, добавление middleware для логирования,
    обработки ошибок, управления транзакциями и т.д.)
    """

    registered_command_handlers: dict[Type[Any], type[CommandHandler]] = {}
    registered_query_handlers: dict[Type[Any], type[QueryHandler]] = {}

    def __init__(
        self,
        logger: Optional[Any] = None,
        props: Optional[dict] = None,
        bus_factory=None,
        register_handlers=None,
    ):
        self.command_context = CommandContext(bus=self, data=props or {})  # Starts empty
        self.logger = logger if logger else logging.getLogger()
        self._bus_factory = bus_factory
        self._register_handlers = register_handlers

    def _spawn(self, *, props=None) -> "CommandBus":
        if self._bus_factory is None:
            raise RuntimeError(
                "Не задан bus factory. Обязателен при использовании bus pattern в multiprocessing"
            )
        bus = self._bus_factory(
            logger=self.logger,
            props=props,
        )
        if self._register_handlers:
            self._register_handlers()
        return bus

    @staticmethod
    def register_handler(command_type, command_handler_type):
        """Регистрация обработчика для конкретного типа команды или запроса. В будущем при необходимости
        проверки на типы, поддержку нескольких обработчиков для одного типа команды и т.д."""
        if issubclass(command_handler_type, QueryHandler):
            CommandBus.registered_query_handlers[command_type] = command_handler_type
        else:
            CommandBus.registered_command_handlers[command_type] = command_handler_type

    def execute(self, command, *args, **kwargs) -> "CommandBus":
        """Выполнение обработчика команды с передачей args/kwargs"""
        handler: CommandHandler = CommandBus.registered_command_handlers[type(command)](
            self.logger, *args, **kwargs
        )
        ret_val = handler.execute(command, self.command_context)  # Updates context immutably
        if isinstance(ret_val, CommandContext):
            self.command_context = ret_val
        if isinstance(ret_val, CommandResult):
            new_dict = self.command_context.data or {}
            if isinstance(ret_val.data, dict):
                new_dict.update(ret_val.data or {})
            self.command_context.data = new_dict
            self.command_context.data[RESULT] = (
                ret_val if isinstance(ret_val, CommandResult) else ret_val.data[RESULT]
            )
        return self

    def then(self, command: Command) -> "CommandBus":
        return self.execute(command)

    def query(self, request: QueryBase[TResult], *args, **kwargs) -> TResult:
        """Выполнение запроса"""
        handler: QueryHandler = CommandBus.registered_query_handlers[type(request)](
            self.logger, *args, **kwargs
        )
        return handler.execute(request)

    def result(self) -> "CommandResult":
        val = self.command_context.data.get(RESULT)
        if val:
            return cast(CommandResult, val)

        raise ValueError("Result not found")

    def execute_background(self, command: "Command", *, name: str) -> "DeferredChain":
        chain = DeferredChain(bus=self, name=name)
        return chain.then(command)


T = TypeVar("T")


@dataclass
class CommandResult:
    """Результат выполнения команды, который может включать в себя флаги успеха, сообщения, ошибки, предупреждения,
    данные и т.д. Сейчас ожидаем что класс JSON-serializable для удобства прямой передачи в API без выделения
    DTO-слоя (временно или навсегда - посмотрим).
    """

    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    infos: List[str] = field(default_factory=list)
    is_success: bool = True
    message: str = ""
    details: Optional[Any] = None
    data: Optional[Any] = None
    request_id: Optional[uuid.UUID] = None
    operation_id: Optional[str] = None

    def get_data(self, t: Type[T], key: str) -> T:
        if self.data is not None:
            return cast(T, self.data[key])
        raise ValueError("Command result data is empty")

    @classmethod
    def from_service_result(cls, service_result: "ServiceResult") -> "CommandResult":
        return CommandResult(
            errors=[x.format_message() for x in service_result._errors],
            warnings=[x.format_message() for x in service_result._warnings],
            infos=[x.format_message() for x in service_result._infos],
        )


class UpdateContextCommand(Command):
    """Пример команды для обновления контекста выполнения в цепочке команд. Команды такого типа могут использоваться для
    передачи данных между командами в рамках одного процесса/операции, не нарушая иммутабельность контекста.
    """

    updates: dict

    @classmethod
    def from_kwargs(cls, **kwargs):
        return cls.model_construct(updates=kwargs)


class UpdateContextHandler(CommandHandler[UpdateContextCommand]):
    """Простой обработчик для UpdateContextCommand"""

    def execute(self, command: UpdateContextCommand, command_context: CommandContext):
        # возвращаем новый контекст (иммутабельный)
        return command_context.updated(**command.updates)


@dataclass
class DeferredChain:
    bus: CommandBus
    name: str
    commands: List[Command] = field(default_factory=list)
    on_success_callback: Optional[Callable[[], None]] = None
    on_failure_callback: Optional[Callable[[str], None]] = None

    def then(self, command: Command) -> "DeferredChain":
        self.commands.append(command)
        return self

    def on_success(self, callback: Callable[[], None]) -> "DeferredChain":
        self.on_success_callback = callback
        return self

    def on_failure(self, callback: Callable[[str], None]) -> "DeferredChain":
        self.on_failure_callback = callback
        return self

    def enqueue(self) -> CommandResult:
        ctx = self.bus.command_context
        scheduler: JobScheduler = ctx.require("scheduler")

        # корреляционные ids
        request_id = (
            ctx.data.get("request_id")
            or RequestManager.create_request_context(
                message="Command chain started in background"
            ).request_id
        )
        operation_id = ctx.data.get("operation_id")
        ctx.data["request_id"] = request_id
        ctx.data["operation_id"] = operation_id

        chain = list(self.commands)

        def _job():
            try:
                for c in chain:
                    _ = self.bus.execute(c)
                    result = self.bus.result()
                    if not result.is_success:
                        message = f"Command chain execution failed on command {str(type(c))}"
                        self.bus.logger.error(message)
                        self._notify_failure(message)
                        RequestManager.update_request_status(
                            request_id, RequestStatus.ERROR, message
                        )
                        return
                RequestManager.update_request_status(
                    request_id, RequestStatus.COMPLETED, "Command chain completed"
                )
                self._notify_success()
                self.bus.logger.info("Command chain completed")
            except Exception as ex:
                self.bus.logger.error(ex)
                self.bus.logger.exception("Deferred chain failed: %s", self.name)
                self._notify_failure(str(ex))
                RequestManager.update_request_status(request_id, RequestStatus.ERROR, str(ex))

        job_id = scheduler.submit(_job, name=self.name)  # type: ignore

        return CommandResult(
            is_success=True,
            message=f"Deferred chain enqueued: {self.name}",
            data={"job_id": job_id, "steps": len(chain)},
            request_id=cast(uuid.UUID, request_id) if request_id else None,
            operation_id=operation_id,
        )

    def _notify_failure(self, message: str) -> None:
        if self.on_failure_callback is None:
            return

        try:
            self.on_failure_callback(message)
        except Exception:
            logging.getLogger(__name__).exception("Deferred chain failure callback failed")

    def _notify_success(self) -> None:
        if self.on_success_callback is None:
            return

        try:
            self.on_success_callback()
        except Exception:
            logging.getLogger(__name__).exception("Deferred chain success callback failed")


CommandBus.register_handler(UpdateContextCommand, UpdateContextHandler)
