from __future__ import annotations

from sqlalchemy.dialects.postgresql.json import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from infrastructure.db.models.base import Base
from infrastructure.db.models.mixins import (
    ActivableMixin,
    IdentifiedTableMixin,
    LoggedTableMixin,
    NamedTableMixin,
    VersionedTableMixin,
)


class LegalEntityDbModel(
    Base,
    IdentifiedTableMixin,
    NamedTableMixin,
    LoggedTableMixin,
    VersionedTableMixin,
    ActivableMixin,
):

    __tablename__ = "legal_entities"

    aliases: Mapped[list[str]] = mapped_column(type_=JSONB)
