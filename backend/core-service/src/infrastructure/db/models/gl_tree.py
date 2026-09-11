from __future__ import annotations

from typing import Any

from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from infrastructure.db.models.base import Base
from infrastructure.db.models.mixins import IdentifiedTableMixin, LoggedTableMixin, NamedTableMixin


class GlTreeDbModel(Base, IdentifiedTableMixin, NamedTableMixin, LoggedTableMixin):
    __tablename__ = "gl_trees"

    filter: Mapped[str | None] = mapped_column(nullable=True)
    options: Mapped[dict[str, Any] | None] = mapped_column(type_=JSONB, nullable=True)
    hierarchy: Mapped[list[dict[str, Any]]] = mapped_column(type_=JSONB)
