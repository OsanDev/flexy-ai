from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from app.media_probe import MediaProbeError, MediaProbeUnavailable, probe_media


def test_probe_returns_stream_metadata(tmp_path: Path):
    media = tmp_path / "sample.mp4"
    media.write_bytes(b"not actually read by mocked ffprobe")
    completed = type("Completed", (), {"returncode": 0, "stdout": json.dumps({
        "format": {"duration": "12.5", "format_name": "mov,mp4"},
        "streams": [{"codec_type": "video", "codec_name": "h264", "width": 1920, "height": 1080}],
    }), "stderr": ""})()
    with patch("app.media_probe.shutil.which", return_value="/usr/bin/ffprobe"), patch(
        "app.media_probe.subprocess.run", return_value=completed
    ):
        result = probe_media(media)
    assert result["duration"] == 12.5
    assert result["streams"][0]["codec_name"] == "h264"
    assert result["streams"][0]["width"] == 1920


def test_probe_rejects_unreadable_media(tmp_path: Path):
    media = tmp_path / "bad.mp4"
    media.write_bytes(b"bad")
    completed = type("Completed", (), {"returncode": 1, "stdout": "", "stderr": "invalid"})()
    with patch("app.media_probe.shutil.which", return_value="/usr/bin/ffprobe"), patch(
        "app.media_probe.subprocess.run", return_value=completed
    ):
        with pytest.raises(MediaProbeError):
            probe_media(media)


def test_probe_fails_closed_when_ffprobe_is_missing(tmp_path: Path):
    with patch("app.media_probe.shutil.which", return_value=None):
        with pytest.raises(MediaProbeUnavailable):
            probe_media(tmp_path / "sample")


def test_storage_persists_probe_metadata(tmp_path: Path):
    from app import storage
    with patch.object(storage, "DATA_DIR", tmp_path), patch.object(storage, "DB_PATH", tmp_path / "test.sqlite3"), patch.object(storage, "MEDIA_DIR", tmp_path / "media"), patch.object(storage, "RENDER_DIR", tmp_path / "renders"):
        storage.init_db()
        storage.save_project("project-1", "Test", {"id": "project-1"})
        storage.add_media({
            "id": "media-1", "project_id": "project-1", "filename": "clip.mp4",
            "stored_name": "media-1.mp4", "mime_type": "video/mp4", "size_bytes": 123,
            "duration": 4.25, "metadata": {"format_name": "mp4", "streams": [{"codec_name": "h264"}]},
        })
        item = storage.get_media("media-1")
        assert item["duration"] == 4.25
        assert item["metadata"]["streams"][0]["codec_name"] == "h264"
        listed = storage.list_project_media("project-1")
        assert listed[0]["metadata"]["format_name"] == "mp4"
