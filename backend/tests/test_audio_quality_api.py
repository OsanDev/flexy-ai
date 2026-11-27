from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app import main, storage


def test_audio_quality_endpoint_returns_calibrated_report(tmp_path: Path, monkeypatch):
    source = tmp_path / "source.wav"
    source.write_bytes(b"audio")
    monkeypatch.setattr(storage, "MEDIA_DIR", tmp_path)
    monkeypatch.setattr(storage, "get_media_for_owner", lambda owner, media, project: {
        "stored_name": source.name,
        "metadata": {"streams": [{"codec_type": "audio"}]},
    })
    expected = {
        "standard": "EBU R128", "integrated_lufs": -16.0,
        "loudness_range_lu": 4.0, "true_peak_dbfs": -1.0,
        "measurements_available": True, "notice": "Read-only measurement.",
    }
    monkeypatch.setattr(main, "analyze_loudness", lambda path: expected)
    result = main.read_audio_quality("project", "media", user=SimpleNamespace(id="owner"))
    assert result == {"media_id": "media", **expected}


def test_audio_quality_endpoint_rejects_non_audio_media(monkeypatch):
    monkeypatch.setattr(storage, "get_media_for_owner", lambda *args: {
        "stored_name": "image.png", "metadata": {"streams": [{"codec_type": "video"}]},
    })
    with pytest.raises(HTTPException) as error:
        main.read_audio_quality("project", "media", user=SimpleNamespace(id="owner"))
    assert error.value.status_code == 415
