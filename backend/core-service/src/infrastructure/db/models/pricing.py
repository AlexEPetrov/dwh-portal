from __future__ import annotations

import datetime
import uuid
from typing import Any, Dict, List, Optional

from sqlalchemy import DateTime, ForeignKey, Index, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from infrastructure.db.models.base import DB_SCHEMA, Base
from infrastructure.db.models.calendars import CalendarDbModel
from infrastructure.db.models.mixins import (
    ActivableMixin,
    CategorizedTableMixin,
    IdentifiedTableMixin,
    LoggedTableMixin,
    NamedTableMixin,
    TaggedTableMixin,
    VersionedTableMixin,
)


class DataSourceDbModel(
    Base,
    IdentifiedTableMixin,
    NamedTableMixin,
    LoggedTableMixin,
    VersionedTableMixin,
    TaggedTableMixin,
    CategorizedTableMixin,
):
    """Описывает подключение к источнику данных и его инициализацию."""

    __tablename__ = "datasources"

    engine: Mapped[str] = mapped_column()
    """Тип движка: 'sql' или 'duckdb'"""

    connection_string: Mapped[Optional[str]] = mapped_column()
    """DSN или connection string"""

    init_sql: Mapped[Optional[str]] = mapped_column()
    """SQL для инициализации сессии"""

    extra_config: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB)
    """Дополнительные настройки подключения"""

    connection_ttl_seconds: Mapped[int] = mapped_column(default=3600)
    """Время жизни подключения в пуле"""

    credentials_ref: Mapped[Optional[str]] = mapped_column()
    """Ссылка на vault/secrets manager"""

    is_active: Mapped[bool] = mapped_column(default=True)
    """Флаг активности"""

    data_sets: Mapped[List["DataSetDbModel"]] = relationship(
        back_populates="data_source", cascade="all, delete-orphan"
    )


class DataSetDbModel(
    Base,
    IdentifiedTableMixin,
    NamedTableMixin,
    LoggedTableMixin,
    VersionedTableMixin,
    TaggedTableMixin,
    CategorizedTableMixin,
):
    """Описывает физический набор данных для переиспользования."""

    __tablename__ = "datasets"

    data_source_id: Mapped[uuid.UUID] = mapped_column(ForeignKey(f"{DB_SCHEMA}.datasources.id"))
    """Ссылка на DataSourceDbModel"""

    data_source: Mapped["DataSourceDbModel"] = relationship(back_populates="data_sets")

    path: Mapped[Optional[str]] = mapped_column()
    """Путь к данным (S3 URI, файл, таблица)"""

    file_format: Mapped[Optional[str]] = mapped_column()
    """'parquet', 'csv', 'json', 'table'"""

    hive_partitioning: Mapped[bool] = mapped_column(default=False)
    """Использовать Hive-партиционирование"""

    partition_columns: Mapped[Optional[List[str]]] = mapped_column(JSONB)
    """Имена колонок из пути"""

    options: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB)
    """Дополнительные опции для read_* функций"""

    required_params: Mapped[Optional[List[str]]] = mapped_column(JSONB)
    """Обязательные параметры для разрешения пути"""


class CurveDefinitionDbModel(
    Base,
    IdentifiedTableMixin,
    NamedTableMixin,
    LoggedTableMixin,
    VersionedTableMixin,
    TaggedTableMixin,
    CategorizedTableMixin,
):

    __tablename__ = "curve_definitions"

    curve_type: Mapped[str] = mapped_column(default="forward")
    curve_point_interval: Mapped[str] = mapped_column(default="day")
    availability_mode: Mapped[str] = mapped_column(default="rolling_days_with_interval_floor")

    observ_days_aheads: Mapped[int] = mapped_column(default=0)
    report_date_aheads: Mapped[int] = mapped_column(default=0)
    dwh_data_source: Mapped[Optional[str]] = mapped_column()
    dwh_data_source_type: Mapped[Optional[str]] = mapped_column()
    dwh_data_params: Mapped[Optional[str]] = mapped_column()

    curve_refs: Mapped[List["IndexElementCurveRefDbModel"]] = relationship(
        back_populates="curve_definition", cascade="all, delete-orphan"
    )
    curves: Mapped[List["CurveDbModel"]] = relationship(
        back_populates="curve_definition", cascade="all, delete-orphan"
    )

    uom: Mapped[Optional[str]] = mapped_column()

    ticker: Mapped[Optional[str]] = mapped_column()
    data_source: Mapped[Optional[str]] = mapped_column()

    calendar_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey(f"{DB_SCHEMA}.calendars.id")
    )
    calendar: Mapped[Optional["CalendarDbModel"]] = relationship()

    source_system_id: Mapped[Optional[str]] = mapped_column()

    # === Новые поля для гибких источников данных ===
    data_source_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey(f"{DB_SCHEMA}.datasources.id")
    )
    """Ссылка на DataSourceDbModel"""

    data_source_ref: Mapped[Optional["DataSourceDbModel"]] = relationship(
        foreign_keys=[data_source_id]
    )

    data_set_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey(f"{DB_SCHEMA}.datasets.id"))
    """Ссылка на DataSetDbModel"""

    data_set_ref: Mapped[Optional["DataSetDbModel"]] = relationship(foreign_keys=[data_set_id])

    query_timeout_seconds: Mapped[Optional[int]] = mapped_column()
    """Таймаут выполнения запроса"""

    cache_enabled: Mapped[bool] = mapped_column(default=True, server_default=text("true"))
    """Разрешено ли кеширование"""


class CurveDbModel(Base, IdentifiedTableMixin, LoggedTableMixin):

    __tablename__ = "curves"

    curve_definition_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(f"{DB_SCHEMA}.curve_definitions.id", ondelete="CASCADE")
    )
    curve_definition: Mapped["CurveDefinitionDbModel"] = relationship(back_populates="curves")

    load_time: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True))

    scenario_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey(f"{DB_SCHEMA}.scenarios.id", ondelete="CASCADE")
    )
    scenario: Mapped["ScenarioDbModel"] = relationship(back_populates="curves")

    curve_points: Mapped[List["CurvePointDbModel"]] = relationship(
        back_populates="curve", cascade="all, delete-orphan"
    )

    version: Mapped[Optional[int]] = mapped_column(autoincrement=True)


class CurvePointDbModel(Base, IdentifiedTableMixin):

    __tablename__ = "curve_points"

    curve_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(f"{DB_SCHEMA}.curves.id", ondelete="CASCADE")
    )
    curve: Mapped["CurveDbModel"] = relationship(back_populates="curve_points")

    curve_definition_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(f"{DB_SCHEMA}.curve_definitions.id")
    )

    observ_date: Mapped[datetime.date] = mapped_column()
    report_date: Mapped[datetime.date] = mapped_column()
    value: Mapped[float] = mapped_column()
    extra_info: Mapped[Optional[str]] = mapped_column()
    source_system_row_id: Mapped[Optional[str]] = mapped_column()
    source_system_entity_id: Mapped[Optional[str]] = mapped_column()


Index(
    "sol_gtrm.curve_points_dates_idx",
    CurvePointDbModel.curve_definition_id,
    CurvePointDbModel.observ_date,
    CurvePointDbModel.report_date,
    postgresql_using="btree",
)


class IndexDbModel(
    Base,
    IdentifiedTableMixin,
    NamedTableMixin,
    LoggedTableMixin,
    VersionedTableMixin,
    TaggedTableMixin,
    CategorizedTableMixin,
):

    __tablename__ = "indexes"

    formula: Mapped[str] = mapped_column()

    index_elements: Mapped[List["IndexElementDbModel"]] = relationship(
        "IndexElementDbModel", back_populates="index", cascade="all, delete-orphan"
    )

    index_refs: Mapped[List["IndexElementIndexRefDbModel"]] = relationship(
        back_populates="index", cascade="all, delete-orphan"
    )

    uom: Mapped[Optional[str]] = mapped_column()


class IndexElementDbModel(Base, IdentifiedTableMixin, LoggedTableMixin):

    __tablename__ = "index_elements"

    name: Mapped[Optional[str]] = mapped_column()  # unique key: name + index_id
    description: Mapped[Optional[str]] = mapped_column()

    index_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(f"{DB_SCHEMA}.indexes.id", ondelete="CASCADE")
    )
    index: Mapped["IndexDbModel"] = relationship("IndexDbModel", back_populates="index_elements")

    indexrefs: Mapped[List["IndexElementIndexRefDbModel"]] = relationship(
        "IndexElementIndexRefDbModel", back_populates="element", cascade="all, delete-orphan"
    )
    curverefs: Mapped[List["IndexElementCurveRefDbModel"]] = relationship(
        "IndexElementCurveRefDbModel", back_populates="element", cascade="all, delete-orphan"
    )

    element_type: Mapped[str] = mapped_column()
    element_properties: Mapped[Dict[str, Any]] = mapped_column(JSONB)

    calendar_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey(f"{DB_SCHEMA}.calendars.id")
    )
    calendar: Mapped[Optional["CalendarDbModel"]] = relationship()


class IndexElementCurveRefDbModel(Base, IdentifiedTableMixin, LoggedTableMixin):

    __tablename__ = "index_element_curverefs"

    element_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(f"{DB_SCHEMA}.index_elements.id", ondelete="CASCADE")
    )
    element: Mapped["IndexElementDbModel"] = relationship(back_populates="curverefs")

    curve_definition_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(f"{DB_SCHEMA}.curve_definitions.id")
    )
    curve_definition: Mapped["CurveDefinitionDbModel"] = relationship(back_populates="curve_refs")


class IndexElementIndexRefDbModel(Base, IdentifiedTableMixin, LoggedTableMixin):

    __tablename__ = "index_element_indexrefs"

    element_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(f"{DB_SCHEMA}.index_elements.id", ondelete="CASCADE")
    )
    element: Mapped["IndexElementDbModel"] = relationship(back_populates="indexrefs")

    index_id: Mapped[uuid.UUID] = mapped_column(ForeignKey(f"{DB_SCHEMA}.indexes.id"))
    index: Mapped["IndexDbModel"] = relationship(back_populates="index_refs")


# class IndexElementContractRefDbModel(Base, IdentifiedTableMixin, LoggedTableMixin):

#     __tablename__ = "index_element_contractrefs"

#     element_id: Mapped[uuid.UUID] = mapped_column(
#         ForeignKey(f"{DB_SCHEMA}.index_elements.id", ondelete="CASCADE")
#     )
#     element: Mapped["IndexElementDbModel"] = relationship(back_populates="contractrefs")

#     contractref: Mapped[str] = mapped_column()


class ScenarioDbModel(
    Base, IdentifiedTableMixin, NamedTableMixin, LoggedTableMixin, ActivableMixin
):

    __tablename__ = "scenarios"

    contracts: Mapped[List["ContractDbModel"]] = relationship(
        back_populates="scenario", cascade="all, delete-orphan"
    )
    curves: Mapped[List["CurveDbModel"]] = relationship(
        back_populates="scenario", cascade="all, delete-orphan"
    )

    aliases: Mapped[List["ScenarioAliasDbModel"]] = relationship(
        back_populates="scenario", cascade="all, delete-orphan"
    )

    contract_pricings: Mapped[List["ContractPricingDbModel"]] = relationship(
        back_populates="scenario", cascade="all, delete-orphan"
    )

    # accrual_pricings: Mapped[List["AccrualPricingDbModel"]] = relationship(
    #     back_populates="scenario", cascade="all, delete-orphan"
    # )


class ScenarioAliasDbModel(
    Base, IdentifiedTableMixin, NamedTableMixin, LoggedTableMixin, VersionedTableMixin
):

    __tablename__ = "scenario_aliases"

    name: Mapped[str] = mapped_column()

    scenario_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(f"{DB_SCHEMA}.scenarios.id", ondelete="CASCADE")
    )
    scenario: Mapped["ScenarioDbModel"] = relationship(back_populates="aliases")
