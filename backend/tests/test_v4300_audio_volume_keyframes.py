from pathlib import Path
from unittest.mock import patch

import pytest

from app.rendering import RenderValidationError, _volume_keyframe_expression, validate_render_graph


@pytest.fixture
def media_dir(tmp_path):
    (tmp_path / "picture.mp4").write_bytes(b"video")
    (tmp_path / "music.wav").write_bytes(b"audio")
    return tmp_path


def _graph(media_dir, keyframes):
    records = {
        "video": {"stored_name": "picture.mp4", "mime_type": "video/mp4"},
        "music": {"stored_name": "music.wav", "mime_type": "audio/wav"},
    }
    with patch("app.rendering.storage.MEDIA_DIR", media_dir), patch(
        "app.rendering.storage.get_media", side_effect=lambda media_id: records.get(media_id)
    ):
        return validate_render_graph({
            "clips": [{"media_id": "video", "duration": 4}],
            "audio_clips": [{"media_id": "music", "duration": 4, "volume": 0.8,
                             "volume_keyframes": keyframes}],
        })


def test_volume_keyframes_are_normalized_and_preserved(media_dir):
    result = _graph(media_dir, [{"time": 0, "volume": 0.2}, {"time": 2.5, "volume": 1.4}])
    assert result["audio_clips"][0]["volume_keyframes"] == [
        {"time": 0.0, "volume": 0.2}, {"time": 2.5, "volume": 1.4}
    ]


@pytest.mark.parametrize("keyframes", [
    "bad", [None], [{"time": True, "volume": 1}], [{"time": 0, "volume": True}],
    [{"time": -0.1, "volume": 1}], [{"time": 4.1, "volume": 1}],
    [{"time": 1, "volume": -0.1}], [{"time": 1, "volume": 2.1}],
    [{"time": 2, "volume": 1}, {"time": 1, "volume": 0.5}],
    [{"time": 1, "volume": 1}, {"time": 1, "volume": 0.5}],
])
def test_invalid_volume_keyframes_are_rejected(media_dir, keyframes):
    with pytest.raises(RenderValidationError, match="keyframe"):
        _graph(media_dir, keyframes)


def test_volume_keyframe_expression_builds_piecewise_linear_curve():
    expression = _volume_keyframe_expression(
        [{"time": 0.0, "volume": 0.2}, {"time": 2.0, "volume": 1.0}], 0.8
    )
    assert expression is not None
    assert "if(lt(t\\,2.000000)" in expression
    assert "0.200000" in expression
    assert "1.000000" in expression


def test_empty_volume_keyframes_keep_legacy_constant_volume():
    assert _volume_keyframe_expression([], 0.65) is None


def test_frontend_timeline_serializes_volume_keyframes():
    root = Path(__file__).resolve().parents[2]
    source = (root / "frontend-reference/apps/web/src/lib/timelineGraph.ts").read_text()
    assert "volumeKeyframes?: Array<{ time: number; volume: number }>" in source
    assert "volume_keyframes: clip.volumeKeyframes ?? []" in source
    composer = (root / "frontend-reference/apps/web/src/components/TimelineComposer.tsx").read_text()
    assert "Add keyframe at playhead" in composer
    assert "Volume automation" in composer


def test_audio_bus_routing_and_mixer_settings_are_normalized(media_dir):
    records = {
        "video": {"stored_name": "picture.mp4", "mime_type": "video/mp4"},
        "music": {"stored_name": "music.wav", "mime_type": "audio/wav"},
    }
    with patch("app.rendering.storage.MEDIA_DIR", media_dir), patch(
        "app.rendering.storage.get_media", side_effect=lambda media_id: records.get(media_id)
    ):
        result = validate_render_graph({
            "clips": [{"media_id": "video", "duration": 4}],
            "audio_clips": [{"media_id": "music", "duration": 4, "role": "music", "bus": "music"}],
            "audio_mixer": {"music": {"gain": 0.65, "muted": True}, "master": {"gain": 1.25}},
        })
    assert result["audio_clips"][0]["bus"] == "music"
    assert result["audio_mixer"]["music"] == {"gain": 0.65, "muted": True}
    assert result["audio_mixer"]["master"] == {"gain": 1.25, "muted": False}
    assert result["audio_mixer"]["dialogue"] == {"gain": 1.0, "muted": False}


@pytest.mark.parametrize("mixer", [
    {"music": {"gain": 2.1}}, {"music": {"gain": True}},
    {"music": {"muted": "yes"}}, {"dialogue": None},
])
def test_invalid_audio_bus_settings_are_rejected(media_dir, mixer):
    records = {
        "video": {"stored_name": "picture.mp4", "mime_type": "video/mp4"},
    }
    with patch("app.rendering.storage.MEDIA_DIR", media_dir), patch(
        "app.rendering.storage.get_media", side_effect=lambda media_id: records.get(media_id)
    ):
        with pytest.raises(RenderValidationError, match="Audio mixer"):
            validate_render_graph({"clips": [{"media_id": "video", "duration": 4}], "audio_mixer": mixer})


def test_invalid_audio_bus_name_is_rejected(media_dir):
    records = {
        "video": {"stored_name": "picture.mp4", "mime_type": "video/mp4"},
        "music": {"stored_name": "music.wav", "mime_type": "audio/wav"},
    }
    with patch("app.rendering.storage.MEDIA_DIR", media_dir), patch(
        "app.rendering.storage.get_media", side_effect=lambda media_id: records.get(media_id)
    ):
        with pytest.raises(RenderValidationError, match="Audio bus"):
            validate_render_graph({"clips": [{"media_id": "video", "duration": 4}],
                                  "audio_clips": [{"media_id": "music", "duration": 4, "bus": "master"}]})
