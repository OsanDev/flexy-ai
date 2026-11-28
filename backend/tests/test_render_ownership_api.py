from fastapi.testclient import TestClient

from app import storage
from app.main import app


def _register(client, email):
    response = client.post(
        "/api/auth/register",
        json={"email": email, "password": "a-long-secure-password"},
        headers={"origin": "http://localhost:5173"},
    )
    assert response.status_code == 201
    return response.json()["id"]


def _headers(client):
    return {
        "origin": "http://localhost:5173",
        "x-csrf-token": client.cookies.get("flexy_csrf", ""),
    }


def test_render_jobs_and_downloads_are_owner_scoped(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    render_dir = data_dir / "renders"
    monkeypatch.setattr(storage, "DATA_DIR", data_dir)
    monkeypatch.setattr(storage, "DB_PATH", data_dir / "flexy.sqlite3")
    monkeypatch.setattr(storage, "MEDIA_DIR", data_dir / "media")
    monkeypatch.setattr(storage, "RENDER_DIR", render_dir)
    monkeypatch.setenv("FLEXY_COOKIE_SECURE", "false")
    storage.init_db()

    owner = TestClient(app, base_url="http://testserver")
    other = TestClient(app, base_url="http://testserver")
    owner_id = _register(owner, "render-owner@example.test")
    _register(other, "render-other@example.test")

    project_id = "render-private-project"
    created = owner.post(
        "/api/projects",
        json={"name": "Private render", "project": {"id": project_id}, "expected_revision": 0},
        headers=_headers(owner),
    )
    assert created.status_code == 200

    job_id = "private-render-job"
    assert storage.create_job_for_owner(owner_id, job_id, project_id)

    render_dir.mkdir(parents=True, exist_ok=True)
    (render_dir / "private-render.mp4").write_bytes(b"rendered-video")
    with storage.connect() as db:
        db.execute(
            "UPDATE render_jobs SET status='completed', progress=100, output_name=? WHERE id=?",
            ("private-render.mp4", job_id),
        )
        db.commit()

    assert owner.get(f"/api/renders/{job_id}").status_code == 200
    assert owner.get(f"/api/renders/{job_id}/download").status_code == 200
    assert other.get(f"/api/renders/{job_id}").status_code == 404
    assert other.get(f"/api/renders/{job_id}/download").status_code == 404
    assert other.post(f"/api/renders/{job_id}/cancel", headers=_headers(other)).status_code == 404
    assert other.delete(f"/api/renders/{job_id}", headers=_headers(other)).status_code == 404
