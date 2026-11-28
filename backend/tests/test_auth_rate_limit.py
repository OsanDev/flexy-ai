from fastapi.testclient import TestClient

from app import storage
from app.main import app


def _client(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    monkeypatch.setattr(storage, "DATA_DIR", data_dir)
    monkeypatch.setattr(storage, "DB_PATH", data_dir / "flexy.sqlite3")
    monkeypatch.setattr(storage, "MEDIA_DIR", data_dir / "media")
    monkeypatch.setattr(storage, "RENDER_DIR", data_dir / "renders")
    storage.init_db()
    monkeypatch.setenv("FLEXY_COOKIE_SECURE", "false")
    return TestClient(app, base_url="http://testserver")


def _headers():
    return {"origin": "http://localhost:5173"}


def test_login_is_rate_limited_after_five_failed_attempts(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    payload = {"email": "editor@example.com", "password": "incorrect-password"}

    for _ in range(5):
        response = client.post("/api/auth/login", json=payload, headers=_headers())
        assert response.status_code == 401

    limited = client.post("/api/auth/login", json=payload, headers=_headers())
    assert limited.status_code == 429
    assert "15 minutes" in limited.json()["detail"]


def test_successful_login_clears_failed_attempt_counter(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    credentials = {"email": "editor@example.com", "password": "a-long-secure-password"}
    assert client.post("/api/auth/register", json=credentials, headers=_headers()).status_code == 201
    assert client.post(
        "/api/auth/logout",
        headers={**_headers(), "x-csrf-token": client.cookies["flexy_csrf"]},
    ).status_code == 200

    wrong = {**credentials, "password": "incorrect-password"}
    for _ in range(4):
        assert client.post("/api/auth/login", json=wrong, headers=_headers()).status_code == 401

    accepted = client.post("/api/auth/login", json=credentials, headers=_headers())
    assert accepted.status_code == 200

    for _ in range(5):
        assert client.post("/api/auth/logout", headers={
            **_headers(), "x-csrf-token": client.cookies["flexy_csrf"]
        }).status_code == 200
        assert client.post("/api/auth/login", json=wrong, headers=_headers()).status_code == 401
