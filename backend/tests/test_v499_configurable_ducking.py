from pathlib import Path
from unittest.mock import patch
import pytest

from app.rendering import RenderValidationError, validate_render_graph


@pytest.fixture
def media_files(tmp_path):
    for name in ("picture.mp4", "voice.wav", "music.wav"):
        (tmp_path / name).write_bytes(b"test")
    return tmp_path


def _validate(media_dir, settings):
    records = {
        "video": {"stored_name": "picture.mp4", "mime_type": "video/mp4"},
        "voice": {"stored_name": "voice.wav", "mime_type": "audio/wav"},
        "music": {"stored_name": "music.wav", "mime_type": "audio/wav"},
    }
    with patch("app.rendering.storage.MEDIA_DIR", media_dir), patch(
        "app.rendering.storage.get_media", side_effect=lambda media_id: records[media_id]
    ):
        return validate_render_graph({
            "clips": [{"media_id": "video", "duration": 3}],
            "audio_clips": [
                {"media_id": "voice", "duration": 3, "role": "dialogue"},
                {"media_id": "music", "duration": 3, "role": "music"},
            ],
            "ducking": True,
            "ducking_settings": settings,
        })


def test_ducking_settings_are_normalized_and_bounded(media_files):
    result = _validate(media_files, {"threshold_db": -30, "ratio": 4, "attack_ms": 35, "release_ms": 700})
    assert result["ducking_settings"] == {
        "threshold_db": -30.0, "ratio": 4.0, "attack_ms": 35.0, "release_ms": 700.0
    }


@pytest.mark.parametrize("settings", [
    {"threshold_db": -41}, {"threshold_db": -5}, {"ratio": 0.9},
    {"ratio": 21}, {"attack_ms": 0}, {"attack_ms": 201},
    {"release_ms": 49}, {"release_ms": 2001}, {"ratio": True},
])
def test_ducking_rejects_out_of_range_or_boolean_values(media_files, settings):
    with pytest.raises(RenderValidationError, match="Ducking"):
        _validate(media_files, settings)


def test_ducking_settings_must_be_an_object(media_files):
    with pytest.raises(RenderValidationError, match="must be an object"):
        _validate(media_files, [])


def test_frontend_exposes_and_serializes_ducking_controls():
    root = Path(__file__).resolve().parents[2]
    graph = (root / "frontend-reference/apps/web/src/lib/timelineGraph.ts").read_text()
    composer = (root / "frontend-reference/apps/web/src/components/TimelineComposer.tsx").read_text()
    assert "ducking_settings" in graph
    assert "thresholdDb" in graph and "releaseMs" in graph
    assert "Enable dialogue-aware music ducking" in composer
    assert "Trigger threshold (dB)" in composer
    assert "Compression ratio" in composer
    assert "Attack (ms)" in composer and "Release (ms)" in composer
