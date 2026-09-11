from __future__ import annotations

from infrastructure.db.models.base import Base
from infrastructure.db.models.mixins import (
    ActivableMixin,
    IdentifiedTableMixin,
    LoggedTableMixin,
    NamedTableMixin,
    VersionedTableMixin,
)


class ProductTypeDbModel(
    Base,
    IdentifiedTableMixin,
    NamedTableMixin,
    LoggedTableMixin,
    VersionedTableMixin,
    ActivableMixin,
):

    __tablename__ = "product_types"
