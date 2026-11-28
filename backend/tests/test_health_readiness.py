from fastapi.responses import Response

from app import storage
from app import main


def test_health_is_not_ready_without_ffmpeg(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    monkeypatch.setattr(storage, "DATA_DIR", data_dir)
    monkeypatch.setattr(storage, "DB_PATH", data_dir / "flexy.sqlite3")
    monkeypatch.setattr(storage, "MEDIA_DIR", data_dir / "media")
    monkeypatch.setattr(storage, "RENDER_DIR", data_dir / "renders")
    storage.init_db()
    monkeypatch.setattr(main.shutil, "which", lambda _binary: None)

    response = main.health()

    assert isinstance(response, Response)
    assert response.status_code == 503
    assert b'"database_available": true' in response.body
    assert b'"storage_available": true' in response.body
    assert b'"ffmpeg_available": false' in response.body
    assert b'"status": "not_ready"' in response.body


def test_health_is_ready_when_storage_and_ffmpeg_are_available(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    monkeypatch.setattr(storage, "DATA_DIR", data_dir)
    monkeypatch.setattr(storage, "DB_PATH", data_dir / "flexy.sqlite3")
    monkeypatch.setattr(storage, "MEDIA_DIR", data_dir / "media")
    monkeypatch.setattr(storage, "RENDER_DIR", data_dir / "renders")
    storage.init_db()
    monkeypatch.setattr(main.shutil, "which", lambda _binary: "/usr/bin/ffmpeg")

    response = main.health()

    assert response["status"] == "ok"
    assert response["database_available"] is True
    assert response["storage_available"] is True
    assert response["ffmpeg_available"] is True
