from __future__ import annotations

import datetime
from typing import Protocol

from domains.catalog.models import CollectionRun


class LineageAdapter(Protocol):
    """Collect data-flow edges into PortalStore and record one collection run."""

    name: str

    def collect(self, now: datetime.datetime | None = None) -> CollectionRun:
        """Materialize lineage from this source. Must not raise across adapters."""
        ...
