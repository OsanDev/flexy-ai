from __future__ import annotations

from pathlib import Path

from app import storage


def test_storage_directories_can_target_persistent_mount(tmp_path: Path, monkeypatch) -> None:
    mount = tmp_path / "persistent-volume"
    monkeypatch.setattr(storage, "DATA_DIR", mount)
    monkeypatch.setattr(storage, "DB_PATH", mount / "flexy.sqlite3")
    monkeypatch.setattr(storage, "MEDIA_DIR", mount / "media")
    monkeypatch.setattr(storage, "RENDER_DIR", mount / "renders")

    with storage.connect() as db:
        db.execute("CREATE TABLE storage_probe (value TEXT)")
        db.execute("INSERT INTO storage_probe(value) VALUES ('ready')")

    assert (mount / "flexy.sqlite3").is_file()
    assert (mount / "media").is_dir()
    assert (mount / "renders").is_dir()
