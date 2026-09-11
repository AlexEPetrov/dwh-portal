from __future__ import annotations

import datetime
import uuid
from typing import List, Optional

from sqlalchemy import JSON, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from infrastructure.db.models.base import DB_SCHEMA, Base
from infrastructure.db.models.mixins import IdentifiedTableMixin


class PricingValuationDbModel(Base, IdentifiedTableMixin):

    __tablename__ = "valuation_pricings"

    description: Mapped[Optional[str]] = mapped_column()

    valuation_id: Mapped[int] = mapped_column(
        ForeignKey(f"{DB_SCHEMA}.valuation_contracts.id", ondelete="CASCADE")
    )
    valuation: Mapped["ContractValuationDbModel"] = relationship(back_populates="pricings")

    volume_to: Mapped[Optional[float]] = mapped_column()
    date_from: Mapped[datetime.date] = mapped_column()

    name: Mapped[Optional[str]] = mapped_column()

    price: Mapped[float] = mapped_column()
    value: Mapped[float] = mapped_column()
    volume: Mapped[float] = mapped_column()
    price_type: Mapped[str] = mapped_column()
    index_name: Mapped[Optional[str]] = mapped_column()
    index_elements: Mapped[List["IndexElementValuationDbModel"]] = relationship(
        back_populates="pricing", cascade="all, delete-orphan"
    )


class IndexElementValuationDbModel(Base, IdentifiedTableMixin):

    __tablename__ = "valuation_pricing_elements"

    pricing_valuation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(f"{DB_SCHEMA}.valuation_pricings.id", ondelete="CASCADE")
    )
    pricing: Mapped["PricingValuationDbModel"] = relationship(back_populates="index_elements")

    value: Mapped[float] = mapped_column()
    element_type: Mapped[str] = mapped_column()
    name: Mapped[str] = mapped_column()
    index_name: Mapped[Optional[str]] = mapped_column()
    curve_name: Mapped[Optional[str]] = mapped_column()
    formula: Mapped[Optional[str]] = mapped_column()
    slug: Mapped[Optional[str]] = mapped_column()
    uom: Mapped[Optional[str]] = mapped_column()


class ContractValuationDbModel(Base, IdentifiedTableMixin):

    __tablename__ = "valuation_contracts"

    name: Mapped[str] = mapped_column()
    slug: Mapped[Optional[str]] = mapped_column()
    scenario_id: Mapped[Optional[uuid.UUID]] = mapped_column()

    valuation_date: Mapped[datetime.date] = mapped_column()
    observation_date: Mapped[datetime.date] = mapped_column()
    start_time: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True))
    finish_time: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column()

    pricings: Mapped[List["PricingValuationDbModel"]] = relationship(
        back_populates="valuation", cascade="all, delete-orphan"
    )
    pricing_uom: Mapped[str] = mapped_column()

    valuation_details: Mapped[str] = mapped_column(JSONB)
    value: Mapped[float] = mapped_column()
    volume: Mapped[float] = mapped_column()
    volume_uom: Mapped[str] = mapped_column()
    waprice: Mapped[float] = mapped_column()

    reportings: Mapped[List["ReportingValuationDbModel"]] = relationship(
        back_populates="valuation", cascade="all, delete-orphan"
    )

    cashflow_forecasts: Mapped[List["CashflowForecastValuationDbModel"]] = relationship(
        back_populates="valuation", cascade="all, delete-orphan"
    )

    valuation_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(f"{DB_SCHEMA}.valuation_runs.id", ondelete="CASCADE")
    )

    country: Mapped[Optional[str]] = mapped_column()
    supply_path: Mapped[Optional[str]] = mapped_column()
    delivery_market: Mapped[Optional[str]] = mapped_column()
    counterparty: Mapped[Optional[str]] = mapped_column()
    product: Mapped[Optional[str]] = mapped_column()


class ValuationRunDbModel(Base, IdentifiedTableMixin):

    __tablename__ = "valuation_runs"

    name: Mapped[Optional[str]] = mapped_column()
    type: Mapped[str] = mapped_column()  # run_mode: 'deterministic' or 'simulation'
    start_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(timezone=True))
    finish_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(timezone=True))
    params: Mapped[JSON] = mapped_column(type_=JSONB)
    status: Mapped[str] = mapped_column(default="created")
    message: Mapped[Optional[str]] = mapped_column()  # Error/success message for the run


class ReportingValuationDbModel(Base, IdentifiedTableMixin):
    """Отчетные значения в необходимых единицах объема и валют"""

    __tablename__ = "valuation_reportings"

    currency: Mapped[str] = mapped_column()
    volume_uom: Mapped[str] = mapped_column()
    pricing_uom: Mapped[str] = mapped_column()

    value: Mapped[float] = mapped_column()
    volume: Mapped[float] = mapped_column()
    waprice: Mapped[float] = mapped_column()

    valuation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(f"{DB_SCHEMA}.valuation_contracts.id", ondelete="CASCADE")
    )
    valuation: Mapped["ContractValuationDbModel"] = relationship(back_populates="reportings")


class CashflowForecastValuationDbModel(Base, IdentifiedTableMixin):
    """Прогнозные значения по платежам"""

    __tablename__ = "valuation_cashflow_forecasts"

    amount: Mapped[float] = mapped_column()
    payment_date: Mapped[datetime.date] = mapped_column()
    payment_type: Mapped[str] = mapped_column()
    description: Mapped[str] = mapped_column()
    currency: Mapped[str] = mapped_column()

    valuation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(f"{DB_SCHEMA}.valuation_contracts.id", ondelete="CASCADE")
    )
    valuation: Mapped["ContractValuationDbModel"] = relationship(
        back_populates="cashflow_forecasts"
    )


# class ValuationAuditMessageDbModel(Base, IdentifiedTableMixin):
#     """Доп. информация для аудита оценки. Здесь только бизнес (не отладочная/диагностическая) информация"""

#     __tablename__ = "valuation_messages"

# valuation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey(f"{DB_SCHEMA}.valuation_contracts.id", ondelete='CASCADE'))
# valuation: Mapped["ContractValuationDbModel"] = relationship(back_populates="audit")

# status: Mapped[str] = mapped_column()
# text: Mapped[str] = mapped_column()


if __name__ == "__main__":

    from sqlalchemy import create_engine

    engine = create_engine(
        "postgresql+psycopg2://postgres:postgres@localhost:5432/testdb", echo=True
    )

    Base.metadata.create_all(engine)
