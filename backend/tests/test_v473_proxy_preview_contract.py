from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi import HTTPException

from app import main


def test_proxy_endpoint_requires_media_owned_by_project():
    with patch.object(main.storage, "get_media_for_owner", return_value=None):
        with pytest.raises(HTTPException) as error:
            main.read_media_proxy("project", "media", user=SimpleNamespace(id="owner"))
    assert error.value.status_code == 404


def test_proxy_endpoint_generates_cached_low_resolution_mp4(tmp_path):
    source_dir = tmp_path / "media"
    proxy_dir = tmp_path / "data"
    source_dir.mkdir()
    source = source_dir / "source.mp4"
    source.write_bytes(b"source-video")
    media = {"stored_name": "source.mp4", "mime_type": "video/mp4"}
    commands = []

    def fake_run(command, **kwargs):
        commands.append(command)
        Path(command[-1]).write_bytes(b"proxy-video")
        return SimpleNamespace(returncode=0, stderr="", stdout="")

    with patch.object(main.storage, "get_media_for_owner", return_value=media):
        with patch.object(main.storage, "MEDIA_DIR", source_dir):
            with patch.object(main.storage, "DATA_DIR", proxy_dir):
                with patch.object(main.shutil, "which", return_value="/usr/bin/ffmpeg"):
                    with patch.object(main.subprocess, "run", side_effect=fake_run):
                        first = main.read_media_proxy("project", "media-id", user=SimpleNamespace(id="owner"))
                        second = main.read_media_proxy("project", "media-id", user=SimpleNamespace(id="owner"))

    assert first.media_type == "video/mp4"
    assert Path(first.path).read_bytes() == b"proxy-video"
    assert second.path == first.path
    assert len(commands) == 1
    assert "scale=w='min(960,iw)':h=-2:force_original_aspect_ratio=decrease,fps=30" in commands[0]
    assert "-crf" in commands[0] and "28" in commands[0]


def test_proxy_endpoint_rejects_non_video_media():
    with patch.object(main.storage, "get_media_for_owner", return_value={
        "stored_name": "still.jpg", "mime_type": "image/jpeg"
    }):
        with pytest.raises(HTTPException) as error:
            main.read_media_proxy("project", "media", user=SimpleNamespace(id="owner"))
    assert error.value.status_code == 415


def test_playback_preview_exposes_opt_in_proxy_switch_and_api():
    root = Path(__file__).resolve().parents[2] / "frontend-reference/apps/web/src"
    component = (root / "components/PlaybackPreview.tsx").read_text()
    api = (root / "lib/mediaApi.ts").read_text()
    composer = (root / "components/TimelineComposer.tsx").read_text()
    assert "Performance preview" in component
    assert "proxyEnabled && proxyUrl ? proxyUrl" in component
    assert "proxyPreview(projectId, activeClip.mediaId)" in component
    assert "proxyPreview(projectId: string, mediaId: string)" in api
    assert "projectId={projectId}" in composer


def test_proxy_route_is_owner_scoped_and_release_version_current():
    main_source = (Path(__file__).resolve().parents[1] / "app/main.py").read_text()
    package = (Path(__file__).resolve().parents[2] / "frontend-reference/apps/web/package.json").read_text()
    assert '@app.get("/api/projects/{project_id}/media/{media_id}/proxy")' in main_source
    assert 'APP_VERSION = "4.6.0"' in main_source
    assert 'version="4.6.0"' in main_source
    assert '"version": "4.6.0"' in package
