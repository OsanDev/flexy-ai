from fastapi.testclient import TestClient
import pytest

from app import main, storage


@pytest.fixture
def duplicate_env(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "DB_PATH", tmp_path / "duplicate.sqlite3")
    monkeypatch.setattr(storage, "MEDIA_DIR", tmp_path / "media")
    monkeypatch.setattr(storage, "RENDER_DIR", tmp_path / "renders")
    storage.init_db()
    monkeypatch.setenv("FLEXY_COOKIE_SECURE", "false")
    monkeypatch.setenv("FLEXY_CORS_ORIGINS", "http://localhost:5173")
    client = TestClient(main.app)
    response = client.post("/api/auth/register", headers={"origin": "http://localhost:5173"},
        json={"email": "duplicate_env@example.test", "password": "correct-horse-battery-77"})
    assert response.status_code == 201, response.text
    return client


def create_source(client):
    response = client.post("/api/projects", json={
        "name": "Original", "project": {"id": "source", "clips": [{"media_id": "media-1"}]},
        "expected_revision": 0,
    })
    assert response.status_code == 200
    storage.ensure_dirs()
    (storage.MEDIA_DIR / "media-1.mp4").write_bytes(b"fake-media-content")
    storage.add_media({
        "id": "media-1", "project_id": "source", "filename": "clip.mp4",
        "stored_name": "media-1.mp4", "mime_type": "video/mp4", "size_bytes": 18,
        "duration": 12.5, "metadata": {"width": 1280},
    })


def test_duplicate_creates_independent_project_and_media(duplicate_env):
    create_source(duplicate_env)
    response = duplicate_env.post("/api/projects/source/duplicate", json={"name": "Remix"})
    assert response.status_code == 201
    duplicate = response.json()
    assert duplicate["name"] == "Remix"
    assert duplicate["revision"] == 1
    assert duplicate["media_count"] == 1

    copied = duplicate_env.get(f"/api/projects/{duplicate['id']}").json()
    original = duplicate_env.get("/api/projects/source").json()
    assert copied["project"]["id"] == duplicate["id"]
    new_media_id = copied["project"]["clips"][0]["media_id"]
    assert new_media_id != "media-1"
    assert original["project"]["clips"][0]["media_id"] == "media-1"

    media = storage.get_media(new_media_id)
    assert media["project_id"] == duplicate["id"]
    assert (storage.MEDIA_DIR / media["stored_name"]).read_bytes() == b"fake-media-content"


def test_duplicate_defaults_name_and_has_separate_revision_history(duplicate_env):
    create_source(duplicate_env)
    response = duplicate_env.post("/api/projects/source/duplicate", json={})
    assert response.status_code == 201
    duplicate_id = response.json()["id"]
    assert response.json()["name"] == "Original copy"
    versions = duplicate_env.get(f"/api/projects/{duplicate_id}/versions").json()["versions"]
    assert [item["revision"] for item in versions] == [1]


def test_duplicate_missing_source_returns_404(duplicate_env):
    response = duplicate_env.post("/api/projects/missing/duplicate", json={})
    assert response.status_code == 404


def test_duplicate_missing_media_fails_without_creating_partial_project(duplicate_env):
    duplicate_env.post("/api/projects", json={
        "name": "Broken", "project": {"id": "broken"}, "expected_revision": 0,
    })
    storage.add_media({
        "id": "lost", "project_id": "broken", "filename": "lost.mp4",
        "stored_name": "lost.mp4", "mime_type": "video/mp4", "size_bytes": 1,
        "duration": 1, "metadata": {},
    })
    response = duplicate_env.post("/api/projects/broken/duplicate", json={})
    assert response.status_code == 409
    assert len(duplicate_env.get("/api/projects").json()["projects"]) == 1
