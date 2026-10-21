import logging
import os
from typing import Any, Optional

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session

from settings.database import DbConnectionSettings


class SessionProvider:
    """Factory for SQLAlchemy ORM sessions used by the Portal store."""

    engine: Engine | None = None

    @staticmethod
    def _init_engine():
        if SessionProvider.engine is None:
            options = DbConnectionSettings()
            if os.path.exists("/.dockerenv") and options.psg_host == "localhost":
                options.psg_host = "host.docker.internal"
            SessionProvider.engine = create_engine(
                f"postgresql+psycopg2://{options.psg_user}:{options.psg_pass}"
                f"@{options.psg_host}:{options.psg_port}/{options.psg_db}",
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
        """Create a new ORM Session."""
        SessionProvider._init_engine()
        return Session(SessionProvider.engine, expire_on_commit=True)

    @staticmethod
    def get_engine():
        SessionProvider._init_engine()
        return SessionProvider.engine


class SessionContext:
    """Own a Session for a scope, or wrap an existing one without closing it."""

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
        return self

    def __exit__(self, type, value, tb):
        if self._private_session:
            self._private_session.close()
