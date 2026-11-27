import pytest
from fastapi.testclient import TestClient
from app import main, storage

ORIGIN = "http://localhost:5173"

@pytest.fixture
def clients(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "DB_PATH", tmp_path / "versions.sqlite3")
    monkeypatch.setattr(storage, "MEDIA_DIR", tmp_path / "media")
    monkeypatch.setattr(storage, "RENDER_DIR", tmp_path / "renders")
    monkeypatch.setenv("FLEXY_COOKIE_SECURE", "false")
    monkeypatch.setenv("FLEXY_CORS_ORIGINS", ORIGIN)
    storage.init_db()
    return TestClient(main.app), TestClient(main.app)

def register(client, email):
    response = client.post("/api/auth/register", headers={"origin": ORIGIN},
                           json={"email": email, "password": "correct-horse-battery-77"})
    assert response.status_code == 201, response.text
    return response.json()["id"]

def save(client, project_id, name, payload, expected):
    response = client.post("/api/projects", json={"name": name,
        "project": {"id": project_id, "payload": payload}, "expected_revision": expected})
    assert response.status_code == 200, response.text
    return response.json()

def test_version_history_is_private_between_accounts(clients):
    owner, stranger = clients
    register(owner, "version-owner@example.test")
    register(stranger, "version-stranger@example.test")
    save(owner, "private-project", "Private", "first", 0)
    save(owner, "private-project", "Private", "second", 1)
    assert [v["revision"] for v in owner.get("/api/projects/private-project/versions").json()["versions"]] == [2, 1]
    assert stranger.get("/api/projects/private-project/versions").status_code == 404
    assert stranger.get("/api/projects/private-project/versions/1").status_code == 404
    assert stranger.post("/api/projects/private-project/versions/1/restore?expected_revision=2").status_code == 404

def test_version_history_requires_login(clients):
    _, stranger = clients
    assert stranger.get("/api/projects/no-project/versions").status_code == 401
    assert stranger.get("/api/projects/no-project/versions/1").status_code == 401

def test_restore_creates_new_revision_and_keeps_history(clients):
    owner, _ = clients
    register(owner, "restore-owner@example.test")
    save(owner, "restore-project", "Draft", "original", 0)
    save(owner, "restore-project", "Draft", "updated", 1)
    response = owner.post("/api/projects/restore-project/versions/1/restore?expected_revision=2")
    assert response.status_code == 200, response.text
    assert response.json()["revision"] == 3
    current = owner.get("/api/projects/restore-project").json()
    assert current["project"]["payload"] == "original"
    versions = owner.get("/api/projects/restore-project/versions").json()["versions"]
    assert [item["revision"] for item in versions] == [3, 2, 1]

def test_restore_rejects_stale_expected_revision(clients):
    owner, _ = clients
    register(owner, "stale-restore@example.test")
    save(owner, "stale-project", "Draft", "one", 0)
    save(owner, "stale-project", "Draft", "two", 1)
    response = owner.post("/api/projects/stale-project/versions/1/restore?expected_revision=1")
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "PROJECT_VERSION_CONFLICT"
