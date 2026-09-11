from fastapi.testclient import TestClient

import api.system as system
from api.host import app

client = TestClient(app)


def test_get_version_returns_content_of_version_file(tmp_path, monkeypatch):
    version_file = tmp_path / "version.txt"
    version_file.write_text("1.2\n", encoding="utf-8")
    monkeypatch.setattr(system, "VERSION_FILE_PATH", version_file)

    response = client.get("/api/system/version")

    assert response.status_code == 200
    assert response.json() == "1.2"


def test_get_version_returns_500_when_version_file_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(system, "VERSION_FILE_PATH", tmp_path / "absent.txt")

    response = client.get("/api/system/version")

    assert response.status_code == 500
    assert response.json() == {"detail": "version.txt not found"}


def test_get_version_trims_surrounding_whitespace(tmp_path, monkeypatch):
    version_file = tmp_path / "version.txt"
    version_file.write_text("  2.0.1  \n", encoding="utf-8")
    monkeypatch.setattr(system, "VERSION_FILE_PATH", version_file)

    response = client.get("/api/system/version")

    assert response.status_code == 200
    assert response.json() == "2.0.1"
