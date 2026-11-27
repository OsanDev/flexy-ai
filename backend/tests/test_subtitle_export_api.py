from fastapi.testclient import TestClient
from app import main, storage

ORIGIN = "http://localhost:5173"


def setup_client(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "DB_PATH", tmp_path / "subtitles.sqlite3")
    monkeypatch.setattr(storage, "DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(storage, "MEDIA_DIR", tmp_path / "media")
    monkeypatch.setattr(storage, "RENDER_DIR", tmp_path / "renders")
    monkeypatch.setenv("FLEXY_COOKIE_SECURE", "false")
    monkeypatch.setenv("FLEXY_CORS_ORIGINS", ORIGIN)
    storage.ensure_dirs()
    storage.init_db()
    return TestClient(main.app)


def test_subtitle_export_requires_authenticated_session(tmp_path, monkeypatch):
    client = setup_client(tmp_path, monkeypatch)
    response = client.post("/api/subtitles/export", json={"segments": [], "format": "srt"})
    assert response.status_code == 401


def test_subtitle_export_requires_csrf_token(tmp_path, monkeypatch):
    client = setup_client(tmp_path, monkeypatch)
    registered = client.post(
        "/api/auth/register", headers={"origin": ORIGIN},
        json={"email": "captions@example.test", "password": "correct-horse-battery-77"},
    )
    assert registered.status_code == 201
    response = client.post("/api/subtitles/export", json={"segments": [], "format": "srt"})
    assert response.status_code == 403


def test_authenticated_subtitle_export_supports_srt_and_vtt(tmp_path, monkeypatch):
    client = setup_client(tmp_path, monkeypatch)
    registered = client.post(
        "/api/auth/register", headers={"origin": ORIGIN},
        json={"email": "subtitle-export@example.test", "password": "correct-horse-battery-77"},
    )
    assert registered.status_code == 201
    csrf = client.cookies.get("flexy_csrf")
    headers = {"origin": ORIGIN, "x-csrf-token": csrf}
    segments = [{"id": "caption-1", "start": 0, "end": 1.25, "text": "Hello FLEXY"}]

    srt = client.post("/api/subtitles/export", headers=headers,
                      json={"segments": segments, "format": "srt"})
    assert srt.status_code == 200
    assert srt.headers["content-type"].startswith("application/x-subrip")
    assert "00:00:00,000 --> 00:00:01,250" in srt.text
    assert "Hello FLEXY" in srt.text

    vtt = client.post("/api/subtitles/export", headers=headers,
                      json={"segments": segments, "format": "vtt"})
    assert vtt.status_code == 200
    assert vtt.headers["content-type"].startswith("text/vtt")
    assert vtt.text.startswith("WEBVTT\n")
    assert "00:00:00.000 --> 00:00:01.250" in vtt.text
