import logging
import os
from typing import Any, Optional, Type, TypeVar

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session

from settings.database import DbConnectionSettings
from shared.repositories.generic_registry import RepositoryRegistryBase
from shared.repositories.generic_repository import GenericRepository
from shared.repositories.repository_factory import RepositoryFactory

TModel = TypeVar("TModel")
TRepository = TypeVar("TRepository")
TImplementation = TypeVar("TImplementation")


class SessionProvider:
    """Фабрика экземпляров ORM Session"""

    engine: Engine | None = None

    @staticmethod
    def _init_engine():
        if SessionProvider.engine is None:
            options = DbConnectionSettings()
            if os.path.exists("/.dockerenv") and options.psg_host == "localhost":
                options.psg_host = "host.docker.internal"
            SessionProvider.engine = create_engine(
                f"postgresql+psycopg2://{options.psg_user}:{options.psg_pass}@{options.psg_host}:{options.psg_port}/{options.psg_db}",
                pool_recycle=options.orm_pool_recycle,
                pool_pre_ping=options.orm_pre_ping,
                echo=options.orm_debug_mode,
            )
            logging.getLogger().info("SQLAlchemy Engine создан")

    @staticmethod
    def close():
        if SessionProvider.engine is not None:
            SessionProvider.engine.dispose()
            SessionProvider.engine = None

    @staticmethod
    def create_session():
        """Создает новый экземпляр Session"""
        SessionProvider._init_engine()
        return Session(SessionProvider.engine, expire_on_commit=True)

    @staticmethod
    def get_engine():
        SessionProvider._init_engine()
        return SessionProvider.engine


class SessionContext:
    """Контекст-менеджмент и враппер для sqlqlchemy session.
    Назначение - создание или переиспользование
    с автоматическим закрытием при выходе из скоупа"""

    def __init__(self, session: Optional[Any] = None):
        if session:
            self.session = session
            self._private_session = None
        else:
            self.session = SessionProvider.create_session()
            self._private_session = self.session

    def commit(self):
        self.session.commit()

    def __enter__(self):
        # self.session.begin()  = не создаем, полагаемся на стандартное поведение
        # Session (создание транзакции автоматически)
        return self

    def __exit__(self, type, value, tb):
        if self._private_session:
            self._private_session.close()


class RepositoryRegistry(SessionContext, RepositoryRegistryBase):
    """Кэш репозиториев."""

    def __init__(self, repository_factory: RepositoryFactory, **kwargs):
        self._base_kwargs = {"session": None}
        self._base_kwargs.update((k, v) for k, v in kwargs.items() if v is not None)
        super().__init__(**self._base_kwargs)
        self.repositories = {}
        self.repository_factory = repository_factory
        self._repo_kwargs = kwargs.copy()
        self._repo_kwargs.update({"session": self.session})

    def get_repository(self, model_type: Type[TModel]) -> GenericRepository[TModel]:
        repo = self.repositories.get(model_type)
        if not repo:
            repo = self.repository_factory.create_repository(model_type, **self._repo_kwargs)
            self.repositories[model_type] = repo
        return repo
