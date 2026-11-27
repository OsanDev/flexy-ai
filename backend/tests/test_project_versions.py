from fastapi.testclient import TestClient
import pytest

from app import main, storage


@pytest.fixture
def version_env(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "DB_PATH", tmp_path / "versions.sqlite3")
    monkeypatch.setattr(storage, "MEDIA_DIR", tmp_path / "media")
    monkeypatch.setattr(storage, "RENDER_DIR", tmp_path / "renders")
    storage.init_db()
    monkeypatch.setenv("FLEXY_COOKIE_SECURE", "false")
    monkeypatch.setenv("FLEXY_CORS_ORIGINS", "http://localhost:5173")
    client = TestClient(main.app)
    response = client.post("/api/auth/register", headers={"origin": "http://localhost:5173"},
        json={"email": "version_env@example.test", "password": "correct-horse-battery-77"})
    assert response.status_code == 201, response.text
    return client


def test_new_project_starts_at_revision_one(version_env):
    response = version_env.post("/api/projects", json={
        "name": "First", "project": {"id": "p1", "tracks": []}, "expected_revision": 0,
    })
    assert response.status_code == 200
    assert response.json()["revision"] == 1
    assert version_env.get("/api/projects/p1").json()["revision"] == 1


def test_project_save_increments_revision(version_env):
    first = version_env.post("/api/projects", json={
        "name": "First", "project": {"id": "p1"}, "expected_revision": 0,
    })
    second = version_env.post("/api/projects", json={
        "name": "Renamed", "project": {"id": "p1", "title": "new"}, "expected_revision": 1,
    })
    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["revision"] == 2


def test_stale_project_save_is_rejected_without_overwriting_cloud(version_env):
    version_env.post("/api/projects", json={
        "name": "First", "project": {"id": "p1", "title": "original"}, "expected_revision": 0,
    })
    current = version_env.post("/api/projects", json={
        "name": "Cloud edit", "project": {"id": "p1", "title": "cloud"}, "expected_revision": 1,
    })
    stale = version_env.post("/api/projects", json={
        "name": "Old tab", "project": {"id": "p1", "title": "stale"}, "expected_revision": 1,
    })
    assert current.status_code == 200
    assert stale.status_code == 409
    assert stale.json()["detail"]["code"] == "PROJECT_VERSION_CONFLICT"
    saved = version_env.get("/api/projects/p1").json()
    assert saved["project"]["title"] == "cloud"
    assert saved["revision"] == 2


def test_missing_project_cannot_be_created_at_nonzero_revision(version_env):
    response = version_env.post("/api/projects", json={
        "name": "Wrong base", "project": {"id": "p1"}, "expected_revision": 4,
    })
    assert response.status_code == 409


def test_project_versions_are_listed_and_previewable(version_env):
    version_env.post("/api/projects", json={
        "name": "First", "project": {"id": "p1", "title": "v1"}, "expected_revision": 0,
    })
    version_env.post("/api/projects", json={
        "name": "Second", "project": {"id": "p1", "title": "v2"}, "expected_revision": 1,
    })
    listing = version_env.get("/api/projects/p1/versions")
    assert listing.status_code == 200
    assert [v["revision"] for v in listing.json()["versions"]] == [2, 1]
    preview = version_env.get("/api/projects/p1/versions/1")
    assert preview.status_code == 200
    assert preview.json()["project"]["title"] == "v1"


def test_restore_creates_new_revision_without_rewinding_history(version_env):
    version_env.post("/api/projects", json={
        "name": "First", "project": {"id": "p1", "title": "v1"}, "expected_revision": 0,
    })
    version_env.post("/api/projects", json={
        "name": "Second", "project": {"id": "p1", "title": "v2"}, "expected_revision": 1,
    })
    restored = version_env.post(
        "/api/projects/p1/versions/1/restore?expected_revision=2"
    )
    assert restored.status_code == 200
    assert restored.json()["revision"] == 3
    assert restored.json()["restored_from_revision"] == 1
    current = version_env.get("/api/projects/p1").json()
    assert current["revision"] == 3
    assert current["project"]["title"] == "v1"
    assert [v["revision"] for v in version_env.get("/api/projects/p1/versions").json()["versions"]] == [3, 2, 1]


def test_restore_rejects_stale_expected_revision(version_env):
    version_env.post("/api/projects", json={
        "name": "First", "project": {"id": "p1", "title": "v1"}, "expected_revision": 0,
    })
    version_env.post("/api/projects", json={
        "name": "Second", "project": {"id": "p1", "title": "v2"}, "expected_revision": 1,
    })
    response = version_env.post(
        "/api/projects/p1/versions/1/restore?expected_revision=1"
    )
    assert response.status_code == 409
    assert version_env.get("/api/projects/p1").json()["project"]["title"] == "v2"


def test_missing_project_version_returns_404(version_env):
    version_env.post("/api/projects", json={
        "name": "First", "project": {"id": "p1"}, "expected_revision": 0,
    })
    assert version_env.get("/api/projects/p1/versions/99").status_code == 404


def test_existing_cookie_session_can_be_restored_after_page_refresh(version_env):
    restored = version_env.get("/api/auth/me")
    assert restored.status_code == 200
    assert restored.json()["email"] == "version_env@example.test"
    assert restored.json()["id"]


def test_session_restore_endpoint_rejects_missing_session():
    from fastapi.testclient import TestClient
    client = TestClient(main.app)
    response = client.get("/api/auth/me")
    assert response.status_code == 401
