from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app import main


def test_audio_beats_endpoint_returns_analysis(monkeypatch):
    monkeypatch.setattr(main.storage, "get_media_for_owner", lambda *args: {
        "stored_name": "track.wav", "metadata": {"streams": [{"codec_type": "audio"}]}
    })
    monkeypatch.setattr(main.storage, "safe_storage_path", lambda *args: Path("/tmp/track.wav"))
    expected = {"beats": [0.5, 1.0, 1.5], "estimated_bpm": 120.0, "confidence": 0.9}
    monkeypatch.setattr(main, "analyze_beats", lambda path: expected)
    result = main.read_audio_beats("project", "media", user=SimpleNamespace(id="owner"))
    assert result == {"media_id": "media", **expected}


def test_audio_beats_endpoint_rejects_video_without_audio(monkeypatch):
    monkeypatch.setattr(main.storage, "get_media_for_owner", lambda *args: {
        "stored_name": "silent.mp4", "metadata": {"streams": [{"codec_type": "video"}]}
    })
    with pytest.raises(HTTPException) as error:
        main.read_audio_beats("project", "media", user=SimpleNamespace(id="owner"))
    assert error.value.status_code == 415
