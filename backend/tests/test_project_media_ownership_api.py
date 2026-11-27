from fastapi.testclient import TestClient

from app import storage
from app import main as main_module
from app.main import app


def _headers(client):
    return {
        "origin": "http://localhost:5173",
        "x-csrf-token": client.cookies.get("flexy_csrf", ""),
    }


def _register(client, email):
    response = client.post(
        "/api/auth/register",
        json={"email": email, "password": "a-long-secure-password"},
        headers={"origin": "http://localhost:5173"},
    )
    assert response.status_code == 201


def test_projects_and_media_are_isolated_between_accounts(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    monkeypatch.setattr(storage, "DATA_DIR", data_dir)
    monkeypatch.setattr(storage, "DB_PATH", data_dir / "flexy.sqlite3")
    monkeypatch.setattr(storage, "MEDIA_DIR", data_dir / "media")
    monkeypatch.setattr(storage, "RENDER_DIR", data_dir / "renders")
    monkeypatch.setenv("FLEXY_COOKIE_SECURE", "false")
    storage.init_db()

    owner = TestClient(app, base_url="http://testserver")
    other = TestClient(app, base_url="http://testserver")
    _register(owner, "owner@example.test")
    _register(other, "other@example.test")

    created = owner.post(
        "/api/projects",
        json={"name": "Private edit", "project": {"id": "private-project"}, "expected_revision": 0},
        headers=_headers(owner),
    )
    assert created.status_code == 200

    monkeypatch.setattr(
        main_module,
        "probe_media",
        lambda _path: {
            "duration": 10.0,
            "streams": [{"codec_type": "video", "codec_name": "h264"}],
        },
    )
    uploaded = owner.post(
        "/api/projects/private-project/media",
        files={"file": ("private.mp4", b"test-media-bytes", "video/mp4")},
        headers=_headers(owner),
    )
    assert uploaded.status_code == 200
    media_id = uploaded.json()["id"]

    # A different authenticated account must not discover or mutate the project.
    assert other.get("/api/projects/private-project").status_code == 404
    assert other.get("/api/projects/private-project/media").status_code == 404
    assert other.get("/api/projects/private-project/versions").status_code == 404
    assert other.patch(
        "/api/projects/private-project/name",
        json={"name": "Stolen project"},
        headers=_headers(other),
    ).status_code == 404
    assert other.post(
        "/api/projects/private-project/duplicate",
        json={},
        headers=_headers(other),
    ).status_code == 404

    # Media IDs alone are not authorization: the parent project's owner is checked.
    assert other.get(f"/api/media/{media_id}").status_code == 404
    assert other.get(
        f"/api/projects/private-project/media/{media_id}/thumbnail",
        headers={"origin": "http://localhost:5173"},
    ).status_code == 404

    # Export validation must reject another account's project before examining its graph.
    preflight = other.post(
        "/api/projects/private-project/render-preflight",
        json={"graph": {}},
        headers=_headers(other),
    )
    assert preflight.status_code == 404

    # The owner can still retrieve the asset after the rejected cross-account requests.
    assert owner.get(f"/api/media/{media_id}").status_code == 200
