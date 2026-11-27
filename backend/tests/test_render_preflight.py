from __future__ import annotations

import pytest

from app import storage
from app.render_preflight import inspect_render
from app.rendering import RenderValidationError


def setup_project(monkeypatch, tmp_path, duration=5.0, owner="project-a"):
    monkeypatch.setattr(storage, "get_project", lambda project_id: {"id": project_id} if project_id == "project-a" else None)
    media = {
        "id": "video-1", "project_id": owner, "filename": "clip.mp4",
        "stored_name": "clip.mp4", "mime_type": "video/mp4", "duration": duration,
    }
    monkeypatch.setattr(storage, "get_media", lambda media_id: media if media_id == "video-1" else None)
    monkeypatch.setattr(storage, "MEDIA_DIR", tmp_path)
    monkeypatch.setattr("app.render_preflight.probe_video_encoders", lambda: {
        "ffmpeg_available": True, "available": ["libx264"], "hardware": [], "error": None,
    })
    (tmp_path / "clip.mp4").write_bytes(b"fixture")


def test_preflight_reports_counts_and_nonblocking_warnings(monkeypatch, tmp_path):
    setup_project(monkeypatch, tmp_path)
    graph = {"clips": [{"media_id": "video-1", "source_start": 0, "duration": 3}],
             "audio_clips": [], "captions": [], "width": 1920, "height": 1080, "frame_rate": 30}
    result = inspect_render("project-a", graph)
    assert result["ready"] is True
    assert result["video_clip_count"] == 1
    assert result["video_duration"] == 3
    assert {w["code"] for w in result["warnings"]} == {"NO_AUDIO_TRACK", "NO_CAPTIONS"}


def test_preflight_rejects_cross_project_media(monkeypatch, tmp_path):
    setup_project(monkeypatch, tmp_path, owner="another-project")
    graph = {"clips": [{"media_id": "video-1", "duration": 2}]}
    with pytest.raises(RenderValidationError, match="belong to this project"):
        inspect_render("project-a", graph)


def test_preflight_rejects_source_range_beyond_duration(monkeypatch, tmp_path):
    setup_project(monkeypatch, tmp_path, duration=5)
    graph = {"clips": [{"media_id": "video-1", "source_start": 4, "duration": 2}]}
    with pytest.raises(RenderValidationError, match="exceeds the source duration"):
        inspect_render("project-a", graph)


def test_preflight_rejects_missing_project(monkeypatch, tmp_path):
    setup_project(monkeypatch, tmp_path)
    with pytest.raises(RenderValidationError, match="Project not found"):
        inspect_render("missing", {"clips": [{"media_id": "video-1", "duration": 1}]})


def test_shared_project_validator_returns_normalized_graph(monkeypatch, tmp_path):
    from app.render_preflight import validate_project_render_graph

    setup_project(monkeypatch, tmp_path)
    graph = {"clips": [{"media_id": "video-1", "source_start": 1, "duration": 2}]}
    normalized, report = validate_project_render_graph("project-a", graph)
    assert normalized["clips"][0]["source_start"] == 1
    assert report["checked_media_count"] == 1


def test_preflight_allows_source_end_within_tolerance(monkeypatch, tmp_path):
    setup_project(monkeypatch, tmp_path, duration=5)
    graph = {"clips": [{"media_id": "video-1", "source_start": 4, "duration": 1.05}]}
    assert inspect_render("project-a", graph)["ready"] is True


def test_preflight_rejects_audio_from_another_project(monkeypatch, tmp_path):
    setup_project(monkeypatch, tmp_path)
    audio = {
        "id": "audio-1", "project_id": "another-project", "filename": "music.mp3",
        "stored_name": "clip.mp4", "mime_type": "audio/mpeg", "duration": 5,
    }
    original_get_media = storage.get_media
    monkeypatch.setattr(storage, "get_media", lambda media_id: audio if media_id == "audio-1" else original_get_media(media_id))
    graph = {
        "clips": [{"media_id": "video-1", "duration": 2}],
        "audio_clips": [{"media_id": "audio-1", "duration": 2}],
    }
    with pytest.raises(RenderValidationError, match="belong to this project"):
        inspect_render("project-a", graph)


def test_render_endpoint_rejects_foreign_project_media(monkeypatch, tmp_path):
    from fastapi import BackgroundTasks, HTTPException
    from app import main
    from app.main import RenderRequest

    setup_project(monkeypatch, tmp_path, owner="another-project")
    monkeypatch.setattr(storage, "get_project_for_owner", lambda owner_id, project_id: {"id": project_id} if owner_id == "test-owner" and project_id == "project-a" else None)
    monkeypatch.setattr(storage, "get_media_for_owner", lambda owner_id, media_id, project_id=None: storage.get_media(media_id))
    graph = {"clips": [{"media_id": "video-1", "duration": 2}]}
    with pytest.raises(HTTPException) as error:
        main.create_render("project-a", RenderRequest(graph=graph), BackgroundTasks(), user=type("User", (), {"id": "test-owner"})())
    assert error.value.status_code == 422
    assert "belong to this project" in error.value.detail



def test_preflight_blocks_when_ffmpeg_is_unavailable(monkeypatch, tmp_path):
    setup_project(monkeypatch, tmp_path)
    monkeypatch.setattr("app.render_preflight.probe_video_encoders", lambda: {
        "ffmpeg_available": False, "available": [], "hardware": [], "error": "missing",
    })
    graph = {"clips": [{"media_id": "video-1", "duration": 2}]}
    report = inspect_render("project-a", graph)
    assert report["ready"] is False
    assert "FFmpeg is not available" in report["message"]
