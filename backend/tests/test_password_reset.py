from fastapi.testclient import TestClient

from app import auth_api, storage
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


def test_password_reset_is_one_time_and_revokes_existing_sessions(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    credentials = {"email": "editor@example.com", "password": "a-long-secure-password"}
    assert client.post("/api/auth/register", json=credentials, headers=_headers()).status_code == 201
    assert client.get("/api/auth/me").status_code == 200

    delivered = {}
    monkeypatch.setattr(
        auth_api, "_send_password_reset_email",
        lambda email, token: delivered.update(email=email, token=token),
    )
    requested = client.post(
        "/api/auth/password-reset/request",
        json={"email": credentials["email"]},
        headers=_headers(),
    )
    assert requested.status_code == 200
    assert delivered["email"] == credentials["email"]

    changed = client.post(
        "/api/auth/password-reset/confirm",
        json={"token": delivered["token"], "new_password": "a-different-secure-password"},
        headers=_headers(),
    )
    assert changed.status_code == 200
    assert changed.json()["password_reset"] is True
    assert client.get("/api/auth/me").status_code == 401

    reused = client.post(
        "/api/auth/password-reset/confirm",
        json={"token": delivered["token"], "new_password": "another-secure-password"},
        headers=_headers(),
    )
    assert reused.status_code == 400

    old_login = client.post("/api/auth/login", json=credentials, headers=_headers())
    assert old_login.status_code == 401
    new_login = client.post(
        "/api/auth/login",
        json={"email": credentials["email"], "password": "a-different-secure-password"},
        headers=_headers(),
    )
    assert new_login.status_code == 200


def test_password_reset_request_does_not_reveal_unknown_accounts(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    known = client.post(
        "/api/auth/password-reset/request",
        json={"email": "known@example.com"},
        headers=_headers(),
    )
    unknown = client.post(
        "/api/auth/password-reset/request",
        json={"email": "unknown@example.com"},
        headers=_headers(),
    )
    assert known.status_code == unknown.status_code == 200
    assert known.json() == unknown.json()


def test_password_reset_rejects_untrusted_origin(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    response = client.post(
        "/api/auth/password-reset/request",
        json={"email": "editor@example.com"},
        headers={"origin": "https://untrusted.example"},
    )
    assert response.status_code == 403
