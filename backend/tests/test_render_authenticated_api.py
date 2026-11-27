import pytest
from fastapi.testclient import TestClient
from app import main, storage

ORIGIN = "http://localhost:5173"

@pytest.fixture
def api_env(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "DB_PATH", tmp_path / "api.sqlite3")
    monkeypatch.setattr(storage, "RENDER_DIR", tmp_path / "renders")
    storage.RENDER_DIR.mkdir()
    storage.init_db()
    monkeypatch.setenv("FLEXY_COOKIE_SECURE", "false")
    monkeypatch.setenv("FLEXY_CORS_ORIGINS", ORIGIN)
    return TestClient(main.app)

def register(client, email):
    response = client.post(
        "/api/auth/register",
        headers={"origin": ORIGIN},
        json={"email": email, "password": "correct-horse-battery-77"},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]

def test_render_history_requires_login(api_env):
    response = api_env.get("/api/projects/project-a/renders")
    assert response.status_code == 401

def test_two_accounts_cannot_read_or_cancel_each_others_render(api_env):
    owner = TestClient(main.app)
    other = TestClient(main.app)
    owner_id = register(owner, "owner@example.test")
    other_id = register(other, "other@example.test")
    assert owner_id != other_id

    project = owner.post("/api/projects", json={
        "name": "Owner project", "project": {"id": "owned-project"},
        "expected_revision": 0,
    })
    assert project.status_code == 200, project.text
    assert storage.create_job_for_owner(owner_id, "owner-render", "owned-project")

    assert owner.get("/api/renders/owner-render").status_code == 200
    assert other.get("/api/renders/owner-render").status_code == 404
    assert other.post("/api/renders/owner-render/cancel").status_code == 404
    assert other.delete("/api/renders/owner-render").status_code == 404

def test_render_download_is_private_and_owner_scoped(api_env):
    owner = TestClient(main.app)
    other = TestClient(main.app)
    owner_id = register(owner, "download-owner@example.test")
    register(other, "download-other@example.test")
    assert owner.post("/api/projects", json={
        "name": "Export project", "project": {"id": "download-project"},
        "expected_revision": 0,
    }).status_code == 200
    assert storage.create_job_for_owner(owner_id, "download-render", "download-project")
    assert storage.start_job("download-render")
    assert storage.complete_job_if_processing("download-render", "download-render.mp4")
    (storage.RENDER_DIR / "download-render.mp4").write_bytes(b"test-mp4")

    response = owner.get("/api/renders/download-render/download")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "private, no-store"
    assert other.get("/api/renders/download-render/download").status_code == 404
