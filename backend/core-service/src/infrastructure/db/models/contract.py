from __future__ import annotations

import datetime
import uuid
from typing import Any, List, Optional

from sqlalchemy import ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from infrastructure.db.models.base import DB_SCHEMA, Base
from infrastructure.db.models.country import CountryDbModel
from infrastructure.db.models.delivery_market import DeliveryMarketDbModel
from infrastructure.db.models.delivery_point import DeliveryPointDbModel
from infrastructure.db.models.legal_entity import LegalEntityDbModel
from infrastructure.db.models.mixins import (
    ActivableMixin,
    CategorizedTableMixin,
    IdentifiedTableMixin,
    LoggedTableMixin,
    NamedTableMixin,
    PaymentTermTableMixin,
    TaggedTableMixin,
    VersionedTableMixin,
)
from infrastructure.db.models.pricing import (
    IndexDbModel,
    ScenarioDbModel,
)
from infrastructure.db.models.products import ProductDbModel
from infrastructure.db.models.supply_path import SupplyPathDbModel
from infrastructure.db.models.supply_region import SupplyRegionDbModel


class ContractDbModel(
    Base,
    IdentifiedTableMixin,
    NamedTableMixin,
    LoggedTableMixin,
    VersionedTableMixin,
    TaggedTableMixin,
    CategorizedTableMixin,
    ActivableMixin,
):

    __tablename__ = "contracts"

    pricings: Mapped[List["ContractPricingDbModel"]] = relationship(
        back_populates="contract", cascade="all, delete-orphan"
    )
    pricing_uom: Mapped[Optional[str]] = mapped_column()
    volume_uom: Mapped[Optional[str]] = mapped_column()

    contract_type: Mapped[str] = mapped_column()

    deliveries: Mapped[List["DeliveryDbModel"]] = relationship(
        back_populates="contract", cascade="all, delete-orphan"
    )

    counterparty_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey(f"{DB_SCHEMA}.legal_entities.id")
    )
    counterparty: Mapped[Optional["LegalEntityDbModel"]] = relationship()

    country_id: Mapped[int] = mapped_column(ForeignKey(f"{DB_SCHEMA}.countries.id"))
    country: Mapped["CountryDbModel"] = relationship()

    scenario_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey(f"{DB_SCHEMA}.scenarios.id")
    )
    scenario: Mapped[Optional["ScenarioDbModel"]] = relationship(
        "ScenarioDbModel", back_populates="contracts"
    )

    supply_path_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey(f"{DB_SCHEMA}.supply_paths.id")
    )
    supply_path: Mapped[Optional["SupplyPathDbModel"]] = relationship()

    supply_region_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey(f"{DB_SCHEMA}.supply_regions.id")
    )
    supply_region: Mapped[Optional["SupplyRegionDbModel"]] = relationship()

    delivery_market_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(f"{DB_SCHEMA}.delivery_markets.id")
    )
    delivery_market: Mapped["DeliveryMarketDbModel"] = relationship()

    reg_number: Mapped[Optional[str]] = mapped_column()

    product_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey(f"{DB_SCHEMA}.products.id"))
    product: Mapped[Optional["ProductDbModel"]] = relationship()

    extra_properties: Mapped[dict[str, Any]] = mapped_column(type_=JSONB)

    pricing_mode: Mapped[str] = mapped_column()

    payment_terms: Mapped[List["PaymentTermDbModel"]] = relationship(
        back_populates="contract", cascade="all, delete-orphan"
    )

    gl_account: Mapped[Optional[str]] = mapped_column()


class ContractPricingDbModel(Base, IdentifiedTableMixin, LoggedTableMixin):

    __tablename__ = "contract_pricings"

    contract_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(f"{DB_SCHEMA}.contracts.id", ondelete="CASCADE")
    )
    contract: Mapped["ContractDbModel"] = relationship(back_populates="pricings")

    description: Mapped[Optional[str]] = mapped_column()

    name: Mapped[Optional[str]] = mapped_column()

    volume_to: Mapped[Optional[float]] = mapped_column()
    date_from: Mapped[Optional[datetime.date]] = mapped_column()
    date_to: Mapped[Optional[datetime.date]] = mapped_column()

    price_type: Mapped[str] = mapped_column()
    fixed_price: Mapped[Optional[float]] = mapped_column()

    index_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey(f"{DB_SCHEMA}.indexes.id"))
    index: Mapped[Optional["IndexDbModel"]] = relationship()

    trade_date: Mapped[Optional[datetime.date]] = mapped_column()

    extra_props: Mapped[dict[str, Any]] = mapped_column(type_=JSONB)

    scenario_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey(f"{DB_SCHEMA}.scenarios.id")
    )
    scenario: Mapped["ScenarioDbModel"] = relationship(
        "ScenarioDbModel", back_populates="contract_pricings"
    )

    multiplier: Mapped[Optional[float]] = mapped_column()


class PaymentTermDbModel(Base, IdentifiedTableMixin, LoggedTableMixin, PaymentTermTableMixin):

    __tablename__ = "contract_payment_terms"

    contract_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(f"{DB_SCHEMA}.contracts.id", ondelete="CASCADE")
    )
    contract: Mapped["ContractDbModel"] = relationship(back_populates="payment_terms")


class DeliveryDbModel(Base, IdentifiedTableMixin, LoggedTableMixin):

    __tablename__ = "contract_deliveries"

    contract_id: Mapped[uuid.UUID] = mapped_column(ForeignKey(f"{DB_SCHEMA}.contracts.id"))
    contract: Mapped["ContractDbModel"] = relationship(back_populates="deliveries")

    index_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey(f"{DB_SCHEMA}.indexes.id"))
    index: Mapped["IndexDbModel"] = relationship()

    delivery_point_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey(f"{DB_SCHEMA}.delivery_points.id")
    )
    delivery_point: Mapped["DeliveryPointDbModel"] = relationship()

    is_active: Mapped[Optional[bool]] = mapped_column()

    description: Mapped[Optional[str]] = mapped_column()

    name: Mapped[Optional[str]] = mapped_column()
