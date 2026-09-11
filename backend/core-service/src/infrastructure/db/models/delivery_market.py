from __future__ import annotations

from infrastructure.db.models.base import Base
from infrastructure.db.models.mixins import ActivableMixin, IdentifiedTableMixin, LoggedTableMixin, NamedTableMixin, VersionedTableMixin


class DeliveryMarketDbModel(Base, IdentifiedTableMixin, NamedTableMixin, LoggedTableMixin, VersionedTableMixin, ActivableMixin):

    __tablename__ = "delivery_markets"  
