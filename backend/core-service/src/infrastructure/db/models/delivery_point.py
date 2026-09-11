from __future__ import annotations

import uuid
from typing import List, Optional

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from infrastructure.db.models.base import DB_SCHEMA, Base
from infrastructure.db.models.mixins import (
    ActivableMixin,
    IdentifiedTableMixin,
    LoggedTableMixin,
    NamedTableMixin,
    VersionedTableMixin,
)


class DeliveryPointDbModel(
    Base,
    IdentifiedTableMixin,
    NamedTableMixin,
    LoggedTableMixin,
    VersionedTableMixin,
    ActivableMixin,
):

    __tablename__ = "delivery_points"

    aliases: Mapped[List["DeliveryPointAliasDbModel"]] = relationship(
        back_populates="delivery_point", cascade="all, delete-orphan"
    )


class DeliveryPointAliasDbModel(
    Base, IdentifiedTableMixin, NamedTableMixin, LoggedTableMixin, VersionedTableMixin
):

    __tablename__ = "delivery_point_aliases"

    name: Mapped[Optional[str]] = mapped_column(unique=True)

    delivery_point_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(f"{DB_SCHEMA}.delivery_points.id", ondelete="CASCADE")
    )
    delivery_point: Mapped["DeliveryPointDbModel"] = relationship(back_populates="aliases")
