import logging

from fastapi.responses import Response

from app import main, storage


def test_health_logs_storage_permission_errors_without_exposing_them(tmp_path, monkeypatch, caplog):
    data_dir = tmp_path / "data"
    monkeypatch.setattr(storage, "DATA_DIR", data_dir)
    monkeypatch.setattr(storage, "DB_PATH", data_dir / "flexy.sqlite3")
    monkeypatch.setattr(storage, "MEDIA_DIR", data_dir / "media")
    monkeypatch.setattr(storage, "RENDER_DIR", data_dir / "renders")

    def deny_storage_access():
        raise PermissionError("simulated persistent-volume permission failure")

    monkeypatch.setattr(storage, "ensure_dirs", deny_storage_access)
    monkeypatch.setattr(main.shutil, "which", lambda _binary: "/usr/bin/ffmpeg")

    with caplog.at_level(logging.ERROR):
        response = main.health()

    assert isinstance(response, Response)
    assert response.status_code == 503
    assert b'"database_available": false' in response.body
    assert b'"storage_available": false' in response.body
    assert b'"ffmpeg_available": true' in response.body
    assert b"simulated persistent-volume permission failure" not in response.body
    assert "FLEXY readiness probe failed while checking storage/database" in caplog.text
    assert "PermissionError" in caplog.text


def test_health_logs_readiness_component_flags_when_ffmpeg_is_missing(tmp_path, monkeypatch, caplog):
    data_dir = tmp_path / "data"
    monkeypatch.setattr(storage, "DATA_DIR", data_dir)
    monkeypatch.setattr(storage, "DB_PATH", data_dir / "flexy.sqlite3")
    monkeypatch.setattr(storage, "MEDIA_DIR", data_dir / "media")
    monkeypatch.setattr(storage, "RENDER_DIR", data_dir / "renders")
    storage.init_db()
    monkeypatch.setattr(main.shutil, "which", lambda _binary: None)

    with caplog.at_level(logging.ERROR):
        response = main.health()

    assert isinstance(response, Response)
    assert response.status_code == 503
    assert "database_available=True" in caplog.text
    assert "storage_available=True" in caplog.text
    assert "ffmpeg_available=False" in caplog.text
    assert '"ffmpeg_path":' not in response.body.decode()
