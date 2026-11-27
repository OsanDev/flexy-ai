from fastapi.testclient import TestClient
import pytest

from app import main, storage


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "DB_PATH", tmp_path / "organization.sqlite3")
    monkeypatch.setattr(storage, "MEDIA_DIR", tmp_path / "media")
    monkeypatch.setattr(storage, "RENDER_DIR", tmp_path / "renders")
    storage.init_db()
    monkeypatch.setenv("FLEXY_COOKIE_SECURE", "false")
    monkeypatch.setenv("FLEXY_CORS_ORIGINS", "http://localhost:5173")
    client = TestClient(main.app)
    response = client.post("/api/auth/register", headers={"origin": "http://localhost:5173"},
        json={"email": "client@example.test", "password": "correct-horse-battery-77"})
    assert response.status_code == 201, response.text
    return client


def create_project(client, project_id, name):
    response = client.post("/api/projects", json={
        "name": name, "project": {"id": project_id, "assets": [], "tracks": []},
        "expected_revision": 0,
    })
    assert response.status_code == 200


def test_project_organization_updates_folder_and_favorite_without_revision(client):
    create_project(client, "p1", "Travel montage")
    response = client.patch("/api/projects/p1/organization", json={
        "folder_name": "Travel", "is_favorite": True,
    })
    assert response.status_code == 200
    assert response.json()["folder_name"] == "Travel"
    assert response.json()["is_favorite"] == 1
    assert response.json()["revision"] == 1
    assert client.get("/api/projects/p1").json()["revision"] == 1


def test_project_list_supports_folder_favorites_and_search(client):
    create_project(client, "p1", "Travel montage")
    create_project(client, "p2", "School edit")
    client.patch("/api/projects/p1/organization", json={"folder_name": "Travel", "is_favorite": True})
    client.patch("/api/projects/p2/organization", json={"folder_name": "School"})

    assert [p["id"] for p in client.get("/api/projects?folder=Travel").json()["projects"]] == ["p1"]
    assert [p["id"] for p in client.get("/api/projects?favorites_only=true").json()["projects"]] == ["p1"]
    assert [p["id"] for p in client.get("/api/projects?search=school").json()["projects"]] == ["p2"]
    assert client.get("/api/projects").json()["folders"] == ["School", "Travel"]


def test_organization_missing_project_returns_404(client):
    response = client.patch("/api/projects/missing/organization", json={"is_favorite": True})
    assert response.status_code == 404


def test_organization_rejects_empty_patch(client):
    create_project(client, "p1", "Travel montage")
    response = client.patch("/api/projects/p1/organization", json={})
    assert response.status_code == 422


def test_project_rename_updates_current_snapshot_without_revision(client):
    create_project(client, "rename-me", "Before")
    response = client.patch("/api/projects/rename-me/name", json={"name": "After"})
    assert response.status_code == 200
    assert response.json()["name"] == "After"
    assert response.json()["revision"] == 1
    assert client.get("/api/projects/rename-me/versions/1").json()["name"] == "After"


def test_project_delete_removes_project_and_version_history(client):
    create_project(client, "delete-me", "Temporary")
    response = client.delete("/api/projects/delete-me")
    assert response.status_code == 200
    assert response.json()["deleted"] is True
    assert client.get("/api/projects/delete-me").status_code == 404
    assert client.get("/api/projects/delete-me/versions").status_code == 404


def test_project_delete_blocks_active_exports(client):
    create_project(client, "busy", "Busy project")
    storage.create_job("active-job", "busy")
    response = client.delete("/api/projects/busy")
    assert response.status_code == 409
    assert client.get("/api/projects/busy").status_code == 200

def test_project_sort_options_are_validated(client):
    create_project(client, "sort-a", "Alpha")
    create_project(client, "sort-z", "Zulu")
    response = client.get("/api/projects?sort=name_asc")
    assert response.status_code == 200
    assert [item["name"] for item in response.json()["projects"]] == ["Alpha", "Zulu"]
    assert client.get("/api/projects?sort=arbitrary").status_code == 422
