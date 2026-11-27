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


def _origin():
    return {"origin": "http://localhost:5173"}


def test_register_creates_account_and_authenticated_session(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    response = client.post(
        "/api/auth/register",
        json={"email": "Editor@Example.com", "password": "a-long-secure-password"},
        headers=_origin(),
    )
    assert response.status_code == 201
    assert response.json()["email"] == "editor@example.com"
    assert client.cookies.get("flexy_session")
    assert client.cookies.get("flexy_csrf")

    session = client.get("/api/auth/me")
    assert session.status_code == 200
    assert session.json()["email"] == "editor@example.com"


def test_login_rejects_wrong_password_and_accepts_correct_password(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    credentials = {"email": "editor@example.com", "password": "a-long-secure-password"}
    created = client.post("/api/auth/register", json=credentials, headers=_origin())
    assert created.status_code == 201

    client.post("/api/auth/logout", headers={**_origin(), "x-csrf-token": client.cookies["flexy_csrf"]})
    rejected = client.post(
        "/api/auth/login",
        json={"email": credentials["email"], "password": "incorrect-password"},
        headers=_origin(),
    )
    assert rejected.status_code == 401

    accepted = client.post("/api/auth/login", json=credentials, headers=_origin())
    assert accepted.status_code == 200
    assert accepted.json()["email"] == credentials["email"]
    assert client.get("/api/auth/me").status_code == 200


def test_register_rejects_duplicate_email_and_untrusted_origin(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    credentials = {"email": "editor@example.com", "password": "a-long-secure-password"}
    assert client.post("/api/auth/register", json=credentials, headers=_origin()).status_code == 201
    duplicate = client.post(
        "/api/auth/register",
        json={"email": "EDITOR@example.com", "password": "another-long-password"},
        headers=_origin(),
    )
    assert duplicate.status_code == 409

    untrusted = client.post(
        "/api/auth/login",
        json=credentials,
        headers={"origin": "https://untrusted.example"},
    )
    assert untrusted.status_code == 403


def test_logout_requires_csrf_and_revokes_session(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    credentials = {"email": "editor@example.com", "password": "a-long-secure-password"}
    assert client.post("/api/auth/register", json=credentials, headers=_origin()).status_code == 201

    denied = client.post("/api/auth/logout", headers=_origin())
    assert denied.status_code == 403

    token = client.cookies["flexy_csrf"]
    logged_out = client.post(
        "/api/auth/logout",
        headers={**_origin(), "x-csrf-token": token},
    )
    assert logged_out.status_code == 200
    assert logged_out.json()["logged_out"] is True
    assert client.get("/api/auth/me").status_code == 401
