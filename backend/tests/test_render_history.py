from fastapi.testclient import TestClient
import pytest

from app import main, storage


@pytest.fixture
def history_env(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "DB_PATH", tmp_path / "history.sqlite3")
    monkeypatch.setattr(storage, "RENDER_DIR", tmp_path / "renders")
    storage.RENDER_DIR.mkdir()
    storage.init_db()
    monkeypatch.setenv("FLEXY_COOKIE_SECURE", "false")
    monkeypatch.setenv("FLEXY_CORS_ORIGINS", "http://localhost:5173")
    client = TestClient(main.app)
    response = client.post("/api/auth/register", headers={"origin": "http://localhost:5173"},
        json={"email": "render-history@example.test", "password": "correct-horse-battery-77"})
    assert response.status_code == 201, response.text
    owner_id = response.json()["id"]
    for project_id, name in (("project-a", "A"), ("project-b", "B")):
        created = client.post("/api/projects", json={"name": name, "project": {"id": project_id}, "expected_revision": 0})
        assert created.status_code == 200, created.text
    client.owner_id = owner_id
    return client


def test_project_render_history_is_scoped_and_newest_first(history_env):
    storage.create_job_for_owner(history_env.owner_id, "old", "project-a")
    storage.create_job_for_owner(history_env.owner_id, "new", "project-a")
    storage.create_job_for_owner(history_env.owner_id, "other-project", "project-b")
    storage.update_job("old", status="failed", progress=0, error="bad export")
    storage.update_job("new", status="cancelled", progress=0)

    response = history_env.get("/api/projects/project-a/renders")
    assert response.status_code == 200
    payload = response.json()["renders"]
    assert {item["id"] for item in payload} == {"old", "new"}
    assert all(item["project_id"] == "project-a" for item in payload)
    assert all("output_name" not in item for item in payload)


def test_history_returns_download_link_only_for_completed_export(history_env):
    storage.create_job_for_owner(history_env.owner_id, "done", "project-a")
    assert storage.start_job("done")
    assert storage.complete_job_if_processing("done", "done.mp4")
    response = history_env.get("/api/projects/project-a/renders")
    item = response.json()["renders"][0]
    assert item["download_url"] == "/api/renders/done/download"


def test_delete_history_removes_completed_file_and_record(history_env):
    storage.create_job_for_owner(history_env.owner_id, "done", "project-a")
    assert storage.start_job("done")
    assert storage.complete_job_if_processing("done", "done.mp4")
    (storage.RENDER_DIR / "done.mp4").write_bytes(b"video")

    response = history_env.delete("/api/renders/done")
    assert response.status_code == 200
    assert response.json()["deleted"] is True
    assert storage.get_job("done") is None
    assert not (storage.RENDER_DIR / "done.mp4").exists()


def test_active_render_cannot_be_deleted(history_env):
    storage.create_job_for_owner(history_env.owner_id, "active", "project-a")
    assert storage.start_job("active")
    response = history_env.delete("/api/renders/active")
    assert response.status_code == 409
    assert storage.get_job("active") is not None


def test_missing_project_history_is_404(history_env):
    response = history_env.get("/api/projects/missing/renders")
    assert response.status_code == 404
