import datetime
import uuid
from typing import Optional

from sqlalchemy import DateTime, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column


class NamedTableMixin:
    name: Mapped[str] = mapped_column(unique=True)
    slug: Mapped[Optional[str]] = mapped_column(unique=True)
    description: Mapped[Optional[str]] = mapped_column()

    def get_slug_or_name(self):
        """Возвращает slug или наименование объекта"""
        name = None
        slug = None

        slug = getattr(self, "slug", "")
        if slug:
            return slug

        name = getattr(self, "name", "")
        return name if name else None

    def __str__(self):
        return self.get_slug_or_name()


class LoggedTableMixin:
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    modified_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.datetime.now, onupdate=datetime.datetime.now
    )


class VersionedTableMixin:
    version: Mapped[int] = mapped_column()
    version_description: Mapped[Optional[str]] = mapped_column()
    author: Mapped[Optional[str]] = mapped_column()
    effective_from: Mapped[Optional[datetime.datetime]] = mapped_column()


class IdentifiedTableMixin:
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )


class CategorizedTableMixin:
    category: Mapped[Optional[str]] = mapped_column()


class TaggedTableMixin:
    tag: Mapped[Optional[str]] = mapped_column()


class ActivableMixin:
    is_active: Mapped[bool] = mapped_column(default=True)


class PaymentTermTableMixin:

    date_offset: Mapped[Optional[int]] = mapped_column()

    date_offset_unit: Mapped[str] = mapped_column()

    amount: Mapped[float] = mapped_column()

    amount_type: Mapped[str] = mapped_column()

    payment_period: Mapped[str] = mapped_column()

    anchor_date: Mapped[str] = mapped_column()
