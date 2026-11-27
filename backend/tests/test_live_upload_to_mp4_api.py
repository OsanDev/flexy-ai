"""Authenticated upload-to-download integration through the real FFmpeg renderer."""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import main, storage
from app.rendering import probe_video_encoders

ORIGIN = "http://localhost:5173"


@pytest.mark.skipif(not shutil.which("ffmpeg") or not shutil.which("ffprobe"), reason="FFmpeg tools are not installed")
def test_authenticated_upload_edit_render_and_mp4_download(tmp_path, monkeypatch):
    if "libx264" not in probe_video_encoders().get("available", []):
        pytest.skip("This FFmpeg build does not include libx264")

    monkeypatch.setattr(storage, "DB_PATH", tmp_path / "flexy.sqlite3")
    monkeypatch.setattr(storage, "DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(storage, "MEDIA_DIR", tmp_path / "media")
    monkeypatch.setattr(storage, "RENDER_DIR", tmp_path / "renders")
    monkeypatch.setenv("FLEXY_COOKIE_SECURE", "false")
    monkeypatch.setenv("FLEXY_CORS_ORIGINS", ORIGIN)
    storage.ensure_dirs()
    storage.init_db()

    source = tmp_path / "source.mp4"
    subprocess.run([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-f", "lavfi", "-i", "testsrc2=size=1280x720:rate=24:duration=1.2",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", str(source),
    ], check=True, capture_output=True, timeout=30)

    with TestClient(main.app) as client:
        registered = client.post(
            "/api/auth/register", headers={"origin": ORIGIN},
            json={"email": "live-export@example.test", "password": "correct-horse-battery-77"},
        )
        assert registered.status_code == 201, registered.text

        project_id = "live-export-project"
        created = client.post("/api/projects", json={
            "name": "Live export integration", "project": {"id": project_id}, "expected_revision": 0,
        })
        assert created.status_code == 200, created.text

        uploaded = client.post(
            f"/api/projects/{project_id}/media",
            files={"file": ("source.mp4", source.read_bytes(), "video/mp4")},
        )
        assert uploaded.status_code == 200, uploaded.text
        media = uploaded.json()
        assert media["size_bytes"] > 1_000
        assert media["duration"] > 1.0

        graph = {
            "clips": [{"media_id": media["id"], "source_start": 0, "duration": 1.0, "timeline_start": 0}],
            "audio_clips": [], "captions": [], "width": 1280, "height": 720,
            "frame_rate": 24, "video_bitrate": "2M",
        }
        preflight = client.post(f"/api/projects/{project_id}/render-preflight", json={"graph": graph})
        assert preflight.status_code == 200, preflight.text
        assert preflight.json()["ready"] is True

        queued = client.post(f"/api/projects/{project_id}/renders", json={"graph": graph})
        assert queued.status_code == 202, queued.text
        render_id = queued.json()["id"]
        status = client.get(f"/api/renders/{render_id}")
        assert status.status_code == 200, status.text
        assert status.json()["status"] == "completed", status.text

        downloaded = client.get(f"/api/renders/{render_id}/download")
        assert downloaded.status_code == 200, downloaded.text
        assert downloaded.headers["content-type"].startswith("video/mp4")
        export_path = tmp_path / "downloaded.mp4"
        export_path.write_bytes(downloaded.content)
        probe = subprocess.run([
            "ffprobe", "-v", "error", "-show_entries",
            "format=format_name,duration:stream=codec_name,width,height,r_frame_rate",
            "-of", "json", str(export_path),
        ], check=True, capture_output=True, text=True, timeout=15)
        report = json.loads(probe.stdout)
        video = next(stream for stream in report["streams"] if stream.get("codec_name"))
        assert video["codec_name"] == "h264"
        assert (video["width"], video["height"]) == (1280, 720)
        assert video["r_frame_rate"] == "24/1"
        assert "mp4" in report["format"]["format_name"]
