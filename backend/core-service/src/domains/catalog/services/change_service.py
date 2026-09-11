from __future__ import annotations

import uuid

from domains.catalog.models import ChangeEvent, ChangeQuery
from domains.catalog.repositories.ports import PortalStore


class ChangeService:
    """Read structural change events from Portal snapshots."""

    def __init__(self, store: PortalStore):
        self._store = store

    def list_changes(self, query: ChangeQuery) -> tuple[list[ChangeEvent], int]:
        return self._store.list_changes(query)

    def get_change(self, change_id: uuid.UUID) -> ChangeEvent | None:
        return self._store.get_change(change_id)
