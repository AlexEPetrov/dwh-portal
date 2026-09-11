from __future__ import annotations

import datetime
import uuid
from typing import List, Optional

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from infrastructure.db.models.base import DB_SCHEMA, Base
from infrastructure.db.models.mixins import IdentifiedTableMixin, LoggedTableMixin, NamedTableMixin


class CalendarDbModel(Base, IdentifiedTableMixin, LoggedTableMixin, NamedTableMixin):

    __tablename__ = "calendars"

    days: Mapped[List["CalendarDayDbModel"]] = relationship(
        back_populates="calendar", cascade="all, delete-orphan"
    )


class CalendarDayDbModel(Base, IdentifiedTableMixin):

    __table_args__ = (
        UniqueConstraint("calendar_id", "date", name="calendar_date_unq"),
        Base.__table_args__,
    )
    __tablename__ = "calendar_days"

    calendar_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(f"{DB_SCHEMA}.calendars.id", ondelete="CASCADE")
    )
    calendar: Mapped["CalendarDbModel"] = relationship(back_populates="days")

    date: Mapped[datetime.date] = mapped_column()
    is_business_day: Mapped[bool] = mapped_column()
    description: Mapped[Optional[str]] = mapped_column()
    is_holiday: Mapped[Optional[bool]] = mapped_column()
    is_weekend: Mapped[Optional[bool]] = mapped_column()
