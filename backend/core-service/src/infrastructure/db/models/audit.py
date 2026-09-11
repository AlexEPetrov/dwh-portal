from __future__ import annotations

import datetime
import uuid
from typing import Any, Dict, Optional

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from infrastructure.db.models.base import Base


class AuditObjectSnapshotDbModel(Base):

    __tablename__ = "audit_object_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    object_id: Mapped[uuid.UUID] = mapped_column()
    object_type: Mapped[str] = mapped_column()
    # Python 3.12 should be:
    # object_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB)
    object_snapshot: Mapped[Dict[str, Any]] = mapped_column(type_=JSONB)
    diff: Mapped[Optional[Dict[str, Any]]] = mapped_column(type_=JSONB)
    version: Mapped[int] = mapped_column()
    version_description: Mapped[Optional[str]] = mapped_column()
    effective_from: Mapped[Optional[datetime.datetime]] = mapped_column()
    author: Mapped[Optional[str]] = mapped_column()
