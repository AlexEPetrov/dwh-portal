from __future__ import annotations

import uuid

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


class GlAccountDbModel(
    Base,
    IdentifiedTableMixin,
    NamedTableMixin,
    LoggedTableMixin,
    VersionedTableMixin,
    ActivableMixin,
):

    __tablename__ = "gl_accounts"

    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey(f"{DB_SCHEMA}.gl_accounts.id"), nullable=True
    )
    parent: Mapped["GlAccountDbModel | None"] = relationship(
        "GlAccountDbModel",
        remote_side="GlAccountDbModel.id",
        back_populates="children",
    )
    children: Mapped[list["GlAccountDbModel"]] = relationship(
        "GlAccountDbModel",
        back_populates="parent",
    )
