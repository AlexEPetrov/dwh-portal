from __future__ import annotations

from urllib.parse import urljoin

import requests

from domains.catalog.providers.lineage import LoaderMetadata
from domains.catalog.providers.python_metadata import parse_loader_metadata
from settings.portal import DwhCollectorSettings


def metadata_url(url_path: str) -> str:
    if url_path.endswith("/metadata"):
        return url_path
    if not url_path.endswith("/"):
        url_path = f"{url_path}/"
    return urljoin(url_path, "metadata")


def resolve_rest_metadata(url_path: str, default_name: str) -> LoaderMetadata:
    """GET {url_path}/metadata without sending runtime payload or headers."""
    settings = DwhCollectorSettings()
    url = metadata_url(url_path)
    last_error = "REST metadata request failed"
    for _ in range(settings.rest_metadata_retries + 1):
        try:
            response = requests.get(url, timeout=settings.rest_metadata_timeout_seconds)
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict):
                return LoaderMetadata(
                    schema_version="1.0",
                    name=default_name,
                    metadata_status="INVALID",
                    diagnostic={"code": "METADATA_INVALID", "message": "REST metadata must be an object"},
                )
            return parse_loader_metadata(payload, default_name=default_name)
        except Exception as exc:
            last_error = str(exc)
    return LoaderMetadata(
        schema_version="1.0",
        name=default_name,
        metadata_status="FAILED",
        diagnostic={"code": "REST_METADATA_UNAVAILABLE", "message": last_error, "url": url},
    )
