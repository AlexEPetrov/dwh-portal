import uuid

from domains.catalog.identity import compute_structure_hash, strip_secrets
from domains.catalog.models import AssetColumn, AssetType


def test_structure_hash_is_stable_for_same_columns():
    asset_id = uuid.uuid4()
    columns = [
        AssetColumn(asset_id=asset_id, ordinal=1, name="id", data_type="bigint", nullable=False),
        AssetColumn(asset_id=asset_id, ordinal=2, name="name", data_type="text", nullable=True),
    ]
    first = compute_structure_hash(AssetType.TABLE, columns)
    second = compute_structure_hash(AssetType.TABLE, list(reversed(columns)))
    assert first == second


def test_strip_secrets_drops_credentials_and_runtime_payload():
    cleaned = strip_secrets(
        {
            "path": "landing/ice/brent",
            "password": "secret",
            "headers": {"Authorization": "Bearer x"},
            "payload": {"body": 1},
            "filename_template": "{date}.csv",
        }
    )
    assert cleaned == {"path": "landing/ice/brent", "filename_template": "{date}.csv"}
