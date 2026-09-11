from typing import List

from fastapi import APIRouter
from fastapi.params import Depends

from api.dependencies.data import session_context
from domains.management.models.base import ObjectInfoModel

#from domains.management.repositories.objectlist_repository import DbObjectListRepository
from infrastructure.db.session_management import SessionContext

scenarios_router = APIRouter(prefix="/scenarios", tags=["scenarios"])


@scenarios_router.get(
    "/", description="Возвращает список сценариев", response_model=List[ObjectInfoModel]
)
def get_scenarios_list(
    data_context: SessionContext = Depends(session_context),
) -> List[ObjectInfoModel]:
    """Возвращает список сценариев"""
    #info_models = DbObjectListRepository(data_context).get_all(ScenarioDbModel)
    return [] #list(info_models)
