from pathlib import Path
from unittest.mock import patch

from app.rendering import EXPORT_PRESETS, validate_render_graph

ROOT = Path(__file__).resolve().parents[2]


def _validate(preset="8k", frame_rate=60):
    media_dir = Path("/tmp/flexy-v470-8k")
    media_dir.mkdir(exist_ok=True)
    (media_dir / "clip.mp4").write_bytes(b"video")
    try:
        with patch("app.rendering.storage.get_media", return_value={
            "stored_name": "clip.mp4", "mime_type": "video/mp4"
        }), patch("app.rendering.storage.MEDIA_DIR", media_dir):
            return validate_render_graph({
                "clips": [{"media_id": "v", "duration": 2}],
                "export_preset": preset,
                "frame_rate": frame_rate,
            })
    finally:
        (media_dir / "clip.mp4").unlink(missing_ok=True)
        media_dir.rmdir()


def test_8k_preset_uses_7680_by_4320_and_high_bitrate():
    graph = _validate()
    assert EXPORT_PRESETS["8k"] == (7680, 4320, "100M")
    assert (graph["width"], graph["height"]) == (7680, 4320)
    assert graph["video_bitrate"] == "100M"


def test_8k_preset_preserves_portrait_orientation():
    media_dir = Path("/tmp/flexy-v470-portrait")
    media_dir.mkdir(exist_ok=True)
    (media_dir / "clip.mp4").write_bytes(b"video")
    try:
        with patch("app.rendering.storage.get_media", return_value={
            "stored_name": "clip.mp4", "mime_type": "video/mp4"
        }), patch("app.rendering.storage.MEDIA_DIR", media_dir):
            graph = validate_render_graph({
                "clips": [{"media_id": "v", "duration": 2}],
                "width": 1080, "height": 1920, "export_preset": "8k",
                "frame_rate": 60,
            })
        assert (graph["width"], graph["height"]) == (4320, 7680)
    finally:
        (media_dir / "clip.mp4").unlink(missing_ok=True)
        media_dir.rmdir()


def test_8k_60fps_is_validated_as_render_target():
    graph = _validate("8k", 60)
    assert graph["frame_rate"] == 60


def test_unsupported_frame_rate_is_rejected():
    import pytest
    from app.rendering import RenderValidationError
    with pytest.raises(RenderValidationError):
        _validate("8k", 144)


def test_export_panel_exposes_8k_and_60fps_and_applies_them_to_requests():
    panel = (ROOT / "frontend-reference/apps/web/src/components/ExportPanel.tsx").read_text()
    assert '<option value="8k">8K UHD (7680 × 4320)</option>' in panel
    assert '<option value="60">60 FPS · Smooth</option>' in panel
    assert "export_preset: exportPreset" in panel
    assert "frame_rate: Number(frameRate)" in panel
    assert "renderApi.create(projectId, exportGraph)" in panel


def test_release_versions_are_updated():
    main = (ROOT / "backend/app/main.py").read_text()
    package = (ROOT / "frontend-reference/apps/web/package.json").read_text()
    assert 'APP_VERSION = "4.6.0"' in main
    assert '"version": "4.6.0"' in package


def test_preflight_warns_that_8k_60fps_is_hardware_intensive():
    source = (ROOT / "backend/app/render_preflight.py").read_text()
    assert 'HIGH_RESOURCE_8K' in source
    assert '8K_60FPS_HEAVY' in source
