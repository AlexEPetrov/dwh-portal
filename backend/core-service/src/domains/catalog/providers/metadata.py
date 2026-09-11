from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from domains.catalog.models import AssetType


@dataclass(frozen=True)
class CatalogObject:
    asset_type: AssetType
    database: str
    schema: str | None
    name: str
    description: str | None = None
    native_id: str | None = None
    columns: list[dict[str, Any]] = field(default_factory=list)
    constraints: list[dict[str, Any]] = field(default_factory=list)
    table_bytes: int | None = None
    index_bytes: int | None = None
    total_bytes: int | None = None
    row_estimate: int | None = None
    attributes: dict[str, Any] = field(default_factory=dict)


class MetadataProvider(Protocol):
    def list_assets(self) -> list[CatalogObject]: ...

    def get_asset(self, qualified_name: str) -> CatalogObject | None: ...
