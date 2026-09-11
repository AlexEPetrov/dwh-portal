from typing import Annotated

from fastapi import Depends

from domains.management.models.lookup_mixin import LookupResolveMixin
from domains.management.repositories import repository_factory
from infrastructure.db.session_management import RepositoryRegistry, SessionContext


def session_context():
    db_session_context = SessionContext()
    try:
        yield db_session_context
    finally:
        db_session_context.__exit__(None, None, None)


def repository_registry(data_context: Annotated[SessionContext, Depends(session_context)]):
    ret = RepositoryRegistry(repository_factory, session=data_context.session)

    LookupResolveMixin.set_repository_registry(ret)

    return ret
