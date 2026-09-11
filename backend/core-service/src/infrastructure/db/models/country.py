from __future__ import annotations

from sqlalchemy.orm import Mapped, mapped_column

from infrastructure.db.models.base import Base
from infrastructure.db.models.mixins import IdentifiedTableMixin


class CountryDbModel(Base, IdentifiedTableMixin):

    __tablename__ = "countries"

    name: Mapped[str] = mapped_column()
    name_full: Mapped[str] = mapped_column()
    name_eng: Mapped[str] = mapped_column()
    name_eng_full: Mapped[str] = mapped_column()
    alpha2_code: Mapped[str] = mapped_column()
    alpha3_code: Mapped[str] = mapped_column()
    numeric_code: Mapped[int] = mapped_column()

    def __str__(self):
        return self.alpha3_code
