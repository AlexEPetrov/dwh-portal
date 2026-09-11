import datetime
import json
from abc import abstractmethod
from inspect import isclass
from typing import (
    Any,
    Callable,
    Dict,
    Generator,
    Generic,
    Iterable,
    Optional,
    Tuple,
    Type,
    TypeVar,
    Union,
    cast,
    get_args,
)

from deepdiff.diff import DeepDiff
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel
from sqlalchemy import and_, inspect, or_
from sqlalchemy.orm import Session

from domains.common.models.mixins import VersionedModelMixin
from domains.management.models.base import AppBaseModel, VersionedObjectModel
from infrastructure.db.data_provider import DataProvider
from infrastructure.db.models.audit import AuditObjectSnapshotDbModel
from infrastructure.db.models.base import Base
from infrastructure.db.models.mixins import IdentifiedTableMixin, VersionedTableMixin
from infrastructure.db.models.pricing import ScenarioDbModel
from infrastructure.db.session_management import SessionContext, SessionProvider
from shared.nullables import require
from shared.repositories.generic_repository import GenericRepository, TModel

TDbModel = TypeVar("TDbModel", bound=Base)


class DbGenericRepository(GenericRepository[TModel], Generic[TModel, TDbModel]):

    def __init__(
        self, session: Union[Session, SessionContext] | None = None, auto_commit: bool = True
    ):
        if session is not None:
            self.session = session.session if isinstance(session, SessionContext) else session
        else:
            self.session = SessionProvider.create_session()
        self.data_provider = DataProvider(self.session)
        self.should_close = session is None
        self.auto_commit = auto_commit

    def __init_subclass__(cls: Type["DbGenericRepository[TModel, TDbModel]"]) -> None:
        if not hasattr(cls, "db_model_class"):
            try:
                # PEP-560
                type_ = get_args(cls.__orig_bases__[0])[
                    1
                ]  # take 2nd generic type argument -DbModel type
                if isclass(type_) and issubclass(type_, Base):
                    cls.db_model_class = type_
                    cls.supports_scenario = hasattr(type_, "scenario_id")
            except Exception as exc:
                msg = "..."
                raise ValueError(msg) from exc

    @abstractmethod
    def map_to_db(self, model: TModel, db_model: TDbModel | None = None) -> TDbModel:
        raise NotImplementedError()

    @abstractmethod
    def map_to_model(self, db_model: TDbModel) -> TModel:
        raise NotImplementedError()

    def get_all(self, scenario: str | None = None) -> Generator[TModel, None, None]:

        if self.__class__.supports_scenario:
            scenario_id = None
            if scenario:
                scenario_entity = self.data_provider.first(
                    ScenarioDbModel, ScenarioDbModel.slug == scenario
                )
                scenario_id = scenario_entity.id
            fullfunc = self.__class__.db_model_class.scenario_id == scenario_id
            query_expr = self.session.query(self.__class__.db_model_class).filter(fullfunc)
        else:
            query_expr = self.session.query(self.__class__.db_model_class)

        return (self.map_to_model(x) for x in query_expr)

    def get_first(self, slug_or_name: str, scenario: str = None) -> Optional[TModel]:

        fullfunc = or_(
            slug_or_name == self.__class__.db_model_class.name,
            slug_or_name == self.__class__.db_model_class.slug,
        )

        if self.__class__.supports_scenario:
            scenario_id = None
            if scenario:
                scenario_entity = self.data_provider.first(
                    ScenarioDbModel, ScenarioDbModel.slug == scenario
                )
                scenario_id = scenario_entity.id
            fullfunc = and_(fullfunc, self.__class__.db_model_class.scenario_id == scenario_id)

        query_expr = self.session.query(self.__class__.db_model_class).filter(fullfunc)

        queried_data = query_expr.first()

        if queried_data is None:
            return None

        return self.map_to_model(queried_data)  # type: ignore

    def get_by_id(self, model_id) -> TModel:
        query_expr = (
            self.session.query(self.__class__.db_model_class)
            .filter(model_id == self.__class__.db_model_class.id)
            .first()
        )
        return self.map_to_model(query_expr)  # type: ignore

    def update(self, model: TModel, entity_find_func: Any = None) -> Tuple[TModel, TDbModel]:
        db_cls = self.__class__.db_model_class

        # 1. Быстрый поиск: session.get эффективнее query.filter
        if entity_find_func is None:
            current_state_db_model = self.session.get(db_cls, getattr(model, "id", None))
        else:
            current_state_db_model = self.session.query(db_cls).filter(entity_find_func).first()

        diff = None

        # 2. Логика версионирования (Type Guard для Pylance)
        # Если модель версионируемая, то и DB-модель тоже (по нашему условию)
        if isinstance(model, VersionedObjectModel) and current_state_db_model:
            # Успокаиваем Pylance для current_state_db_model
            db_model_v = cast(VersionedTableMixin, current_state_db_model)

            if isinstance(db_model_v, IdentifiedTableMixin):
                model.id = db_model_v.id

            diff = self._get_current_snapshot_diff(model)
            if not diff:
                return model, cast(TDbModel, current_state_db_model)

            model.version = db_model_v.version + 1

        # 3. Маппинг
        entity = self.map_to_db(model, cast(TDbModel, current_state_db_model))

        # 4. Синхронизация полей версии (снова используем тот же Guard)
        if isinstance(model, VersionedObjectModel):
            # Cast здесь гарантирует Pylance, что у entity есть эти поля
            entity_v = cast(VersionedTableMixin, entity)
            entity_v.version_description = model.version_description
            entity_v.version = model.version
            entity_v.author = model.author

        # 5. Оптимизация состояния сессии
        state = inspect(entity)
        if state.detached or not state.has_identity:
            self.session.add(entity)

        self.session.flush()

        # 6. Финализация
        if isinstance(entity, IdentifiedTableMixin) and isinstance(model, VersionedObjectModel):
            model.id = entity.id

        if isinstance(model, VersionedObjectModel):
            self._save_version_snapshot(model, diff)

        if self.auto_commit:
            self.session.commit()

        return model, cast(TDbModel, entity)

    def delete(self, slug: str) -> None:
        raise NotImplementedError()

    def close(self):
        if self.should_close:
            self.session.close()

    def _save_version_snapshot(self, model: TModel, diff):
        audit_entity = AuditObjectSnapshotDbModel()
        if isinstance(model, AppBaseModel):
            audit_entity.object_id = require(model.id)
            audit_entity.object_snapshot = model.model_dump(mode="json")
        audit_entity.object_type = str(model.__class__)
        if isinstance(model, VersionedModelMixin):
            audit_entity.version = model.version
            audit_entity.version_description = model.version_description
            audit_entity.author = model.author
        audit_entity.effective_from = datetime.datetime.now()

        if diff:
            # результат diff.to_dict некорректно сериализуется. Поэтому через строку to_json:
            audit_entity.diff = json.loads(diff.to_json())
        self.session.add(audit_entity)
        self.session.flush()

    def _get_current_snapshot_diff(self, model: TModel) -> DeepDiff | None:
        previous_versions_rows = self.data_provider.filter_by_max(
            AuditObjectSnapshotDbModel,
            AuditObjectSnapshotDbModel.effective_from,
            AuditObjectSnapshotDbModel.object_id == model.id,
        )
        if not previous_versions_rows:
            return None
        previous_version_data = previous_versions_rows[0].object_snapshot
        if "id" in previous_version_data:
            del previous_version_data["id"]
        if "version" in previous_version_data:
            del previous_version_data["version"]
        # model_dump недостаточно из-за Enum. См https://stackoverflow.com/questions/65209934/pydantic-enum-field-does-not-get-converted-to-string
        # поэтому заворачиваем в jsonable_encoder
        current_version = jsonable_encoder(
            cast(BaseModel, model).model_dump(exclude={"version", "id"}, mode="python")
        )
        return DeepDiff(previous_version_data, current_version)


class DbCacheableRepository(DbGenericRepository[TModel, TDbModel], Generic[TModel, TDbModel]):
    """Репозиторий с кешированием. Кешируется весь набор данных, поэтому подходит для справочников и других небольших
    по объему данных сущностей (до нескольких тысяч записей).
    Кеширование возможно в т.ч. по сценарию, если сущность поддерживает сценарий (имеет поле scenario_id).
    Внимание: по сути это мемоизация. Поэтому:
        только для маленьких таблиц / справочников
        только для read-heavy hot path
        индекс строится целиком через get_all
        cache lifetime = lifetime repo instance
    Использование: наследовать, реализовать map* методы. См. риск домен.
    """

    def __init_subclass__(cls: Type["DbCacheableRepository[TModel, TDbModel]"]) -> None:
        if not hasattr(cls, "db_model_class"):
            try:
                # PEP-560
                type_ = get_args(cls.__orig_bases__[0])[
                    1
                ]  # take 2nd generic type argument -DbModel type
                if not issubclass(type_, Base):
                    msg = "..."
                    raise ValueError("")
                cls.db_model_class = type_
                cls.supports_scenario = hasattr(type_, "scenario_id")
            except Exception as exc:
                msg = "..."
                raise ValueError(msg) from exc

    def __init__(self, session: Session | None = None, auto_commit: bool = True):
        super().__init__(session, auto_commit)
        self.cached_items = {}

    def get_first(self, slug_or_name: str, scenario: str | None = None) -> TModel:
        scenario_items_dict = self.cached_items.get((scenario))
        if not scenario_items_dict:
            self.cached_items[scenario] = {
                x.get_slug_or_name(): x for x in super().get_all(scenario)  # type: ignore
            }
            cached = self.cached_items[scenario].get(slug_or_name)
        else:
            cached = scenario_items_dict.get(slug_or_name)
        return cached

    def get_all(self, scenario: str | None = None) -> Iterable[TModel]:
        cached = self.cached_items.get(scenario)
        if cached:
            return cached.values()
        else:
            data = [x for x in super().get_all(scenario)]
            self.cached_items[scenario] = {x.get_slug_or_name(): x for x in data}  # type: ignore
            return data

    def update(
        self, model: TModel, entity_find_func: Callable[[], bool] | None = None
    ) -> Tuple[TModel, TDbModel]:
        model, db_model = super().update(model, entity_find_func)
        self._cache_item(model)
        return model, db_model

    def cache(self):
        scenarios = self.data_provider.all(ScenarioDbModel)
        self.cached_items.clear()
        _ = self.get_all()
        for sc in scenarios:
            _ = self.get_all(sc.get_slug_or_name())

    def where(self, conditions: Dict[str, Any]) -> Generator[TModel, None, None]:
        all = self.get_all()
        return self._filter_by_properties(all, conditions)

    def _cache_item(self, model: TModel):
        if self.supports_scenario:
            scenario = model.scenario
        else:
            scenario = None
        self.cached_items[scenario][model.get_slug_or_name()] = model

    def _filter_by_properties(self, collection, filter_dict):
        if not filter_dict:
            return collection.copy()

        filtered = []
        for obj in collection:
            matches = True
            for prop, value in filter_dict.items():
                obj_value = getattr(obj, prop, None)
                if isinstance(value, list) and all(isinstance(item, str) for item in value):
                    values = []
                    for item in value:
                        values += item.split("|")
                elif isinstance(value, str):
                    values = str(value).split("|")
                else:
                    values = [value]
                try:
                    matches_any = False
                    for val in values:
                        if obj_value == val:
                            matches_any = True
                            break
                    if not matches_any:
                        matches = False
                        break

                except (AttributeError, TypeError):
                    matches = False
                    break
                if not matches:
                    break

            if matches:
                filtered.append(obj)

        return filtered
