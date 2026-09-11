from pathlib import Path
from unittest.mock import Mock

import pytest
from gp134.tools.storage_lib import LocalBackend, StorageFS

from domains.risk.services.simulation_curve_file_mapping import load_simulation_curve_file_mapping


def _source_path(tmp_path: Path):
    fs = StorageFS(LocalBackend(), str(tmp_path))
    return fs / "executions/mcmf/observation_date=20260101/operation_id=stress"


def _curve(name: str, slug: str | None = None):
    curve = Mock()
    curve.name = name
    curve.get_slug_or_name.return_value = slug or name
    return curve


def test_mapping_falls_back_to_curve_name_when_manifest_absent(tmp_path):
    mapping = load_simulation_curve_file_mapping(_source_path(tmp_path))

    assert mapping.file_stem_for_curve(_curve("BRENT_DATED")) == "BRENT_DATED"


def test_global_root_manifest_maps_curve_to_file_stem(tmp_path):
    root = tmp_path / "executions" / "mcmf"
    root.mkdir(parents=True)
    (root / "_curve_file_mapping.json").write_text(
        '{"curve_to_file_stem": {"BRENT_DATED": "brent"}}', encoding="utf-8"
    )

    mapping = load_simulation_curve_file_mapping(_source_path(tmp_path))

    assert mapping.file_stem_for_curve(_curve("BRENT_DATED")) == "brent"


def test_file_path_prefers_canonical_curve_file_before_mapping(tmp_path):
    root = tmp_path / "executions" / "mcmf"
    source = root / "observation_date=20260101" / "operation_id=stress"
    source.mkdir(parents=True)
    (root / "_curve_file_mapping.json").write_text(
        '{"curve_to_file_stem": {"BRENT_DATED": "brent"}}', encoding="utf-8"
    )
    (source / "BRENT_DATED.parquet").write_text("", encoding="utf-8")

    source_path = _source_path(tmp_path)
    mapping = load_simulation_curve_file_mapping(source_path)

    assert mapping.file_path_for_curve(
        source_path, _curve("BRENT_DATED"), "parquet"
    ).full_path.endswith("BRENT_DATED.parquet")


def test_file_path_uses_mapping_when_canonical_curve_file_absent(tmp_path):
    root = tmp_path / "executions" / "mcmf"
    root.mkdir(parents=True)
    (root / "_curve_file_mapping.json").write_text(
        '{"curve_to_file_stem": {"BRENT_DATED": "brent"}}', encoding="utf-8"
    )

    source_path = _source_path(tmp_path)
    mapping = load_simulation_curve_file_mapping(source_path)

    assert mapping.file_path_for_curve(
        source_path, _curve("BRENT_DATED"), "parquet"
    ).full_path.endswith("brent.parquet")


def test_source_manifest_overrides_global_manifest(tmp_path):
    root = tmp_path / "executions" / "mcmf"
    source = root / "observation_date=20260101" / "operation_id=stress"
    source.mkdir(parents=True)
    (root / "_curve_file_mapping.json").write_text(
        '{"curve_to_file_stem": {"BRENT_DATED": "brent-global"}}', encoding="utf-8"
    )
    (source / "_curve_file_mapping.json").write_text(
        '{"curve_to_file_stem": {"BRENT_DATED": "brent-source"}}', encoding="utf-8"
    )

    mapping = load_simulation_curve_file_mapping(_source_path(tmp_path))

    assert mapping.file_stem_for_curve(_curve("BRENT_DATED")) == "brent-source"


def test_mapping_uses_curve_slug_identity(tmp_path):
    root = tmp_path / "executions" / "mcmf"
    root.mkdir(parents=True)
    (root / "_curve_file_mapping.json").write_text(
        '{"curve_to_file_stem": {"brent_slug": "brent"}}', encoding="utf-8"
    )

    mapping = load_simulation_curve_file_mapping(_source_path(tmp_path))

    assert mapping.file_stem_for_curve(_curve("BRENT_DATED", slug="brent_slug")) == "brent"


def test_mapping_rejects_path_like_or_extension_file_stem(tmp_path):
    root = tmp_path / "executions" / "mcmf"
    root.mkdir(parents=True)
    (root / "_curve_file_mapping.json").write_text(
        '{"curve_to_file_stem": {"BRENT_DATED": "bad/name"}}', encoding="utf-8"
    )

    with pytest.raises(ValueError, match="Invalid file stem"):
        load_simulation_curve_file_mapping(_source_path(tmp_path))
