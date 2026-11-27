from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi import HTTPException

from app import main


def test_proxy_lock_registry_returns_same_lock_for_same_media():
    first = main._proxy_lock("asset-a")
    second = main._proxy_lock("asset-a")
    other = main._proxy_lock("asset-b")
    assert first is second
    assert first is not other


def test_proxy_endpoint_serializes_cache_generation_and_reuses_result(tmp_path):
    source_dir = tmp_path / "media"
    data_dir = tmp_path / "data"
    source_dir.mkdir()
    (source_dir / "source.mp4").write_bytes(b"source")
    media = {"stored_name": "source.mp4", "mime_type": "video/mp4"}
    calls = []

    def fake_run(command, **kwargs):
        calls.append(command)
        Path(command[-1]).write_bytes(b"proxy")
        return SimpleNamespace(returncode=0, stderr="", stdout="")

    with patch.object(main.storage, "get_media_for_owner", return_value=media):
        with patch.object(main.storage, "MEDIA_DIR", source_dir):
            with patch.object(main.storage, "DATA_DIR", data_dir):
                with patch.object(main.shutil, "which", return_value="/usr/bin/ffmpeg"):
                    with patch.object(main.subprocess, "run", side_effect=fake_run):
                        a = main.read_media_proxy("project", "asset-a", user=SimpleNamespace(id="owner"))
                        b = main.read_media_proxy("project", "asset-a", user=SimpleNamespace(id="owner"))
    assert a.path == b.path
    assert len(calls) == 1


def test_scrubbing_is_coalesced_to_animation_frames():
    source = (Path(__file__).resolve().parents[2] /
              "frontend-reference/apps/web/src/components/PlaybackPreview.tsx").read_text()
    assert "scheduleScrub" in source
    assert "requestAnimationFrame" in source
    assert "cancelAnimationFrame" in source
    assert "onChange={(event) => scheduleScrub(Number(event.target.value))}" in source


def test_release_version_and_proxy_lock_contract():
    main_source = (Path(__file__).resolve().parents[1] / "app/main.py").read_text()
    package = (Path(__file__).resolve().parents[2] /
               "frontend-reference/apps/web/package.json").read_text()
    assert 'APP_VERSION = "4.6.0"' in main_source
    assert 'version="4.6.0"' in main_source
    assert '"version": "4.6.0"' in package
    assert "with _proxy_lock(media_id):" in main_source


def test_proxy_still_rejects_missing_owner_asset():
    with patch.object(main.storage, "get_media_for_owner", return_value=None):
        with pytest.raises(HTTPException) as error:
            main.read_media_proxy("project", "missing", user=SimpleNamespace(id="owner"))
    assert error.value.status_code == 404
