from pathlib import Path
from unittest.mock import patch

from app.rendering import EXPORT_PRESETS, validate_render_graph

ROOT = Path(__file__).resolve().parents[2]


def _validate(preset, fps=120, portrait=False):
    media_dir = Path("/tmp/flexy-v471-120fps")
    media_dir.mkdir(exist_ok=True)
    (media_dir / "clip.mp4").write_bytes(b"video")
    graph = {"clips": [{"media_id": "v", "duration": 2}],
             "export_preset": preset, "frame_rate": fps}
    if portrait:
        graph.update({"width": 1080, "height": 1920})
    try:
        with patch("app.rendering.storage.get_media", return_value={
            "stored_name": "clip.mp4", "mime_type": "video/mp4"
        }), patch("app.rendering.storage.MEDIA_DIR", media_dir):
            return validate_render_graph(graph)
    finally:
        (media_dir / "clip.mp4").unlink(missing_ok=True)
        media_dir.rmdir()


def test_2k_preset_dimensions_and_120fps_bitrate():
    assert EXPORT_PRESETS["2k"] == (2560, 1440, "24M")
    graph = _validate("2k")
    assert (graph["width"], graph["height"]) == (2560, 1440)
    assert graph["frame_rate"] == 120
    assert graph["video_bitrate"] == "36M"


def test_1080p_120fps_supported_with_increased_target_bitrate():
    graph = _validate("1080p")
    assert (graph["width"], graph["height"]) == (1920, 1080)
    assert graph["video_bitrate"] == "18M"


def test_4k_120fps_supported_with_increased_target_bitrate():
    graph = _validate("4k")
    assert (graph["width"], graph["height"]) == (3840, 2160)
    assert graph["video_bitrate"] == "52M"


def test_portrait_2k_120fps_orientation_is_preserved():
    graph = _validate("2k", portrait=True)
    assert (graph["width"], graph["height"]) == (1440, 2560)


def test_invalid_frame_rate_still_rejected():
    import pytest
    from app.rendering import RenderValidationError
    with pytest.raises(RenderValidationError):
        _validate("4k", fps=144)


def test_export_ui_exposes_2k_and_120fps_and_sends_them():
    panel = (ROOT / "frontend-reference/apps/web/src/components/ExportPanel.tsx").read_text()
    assert '<option value="2k">2K QHD (2560 × 1440)</option>' in panel
    assert '<option value="120" disabled={exportPreset === "8k"}>120 FPS · High frame rate (up to 4K)</option>' in panel
    assert "frame_rate: Number(frameRate)" in panel
    assert "renderApi.create(projectId, exportGraph)" in panel


def test_preflight_explains_120fps_source_and_resource_requirements():
    source = (ROOT / "backend/app/render_preflight.py").read_text()
    assert "HIGH_FRAME_RATE_120" in source
    assert "source footage recorded at 120 FPS" in source


def test_release_version_is_updated():
    main = (ROOT / "backend/app/main.py").read_text()
    package = (ROOT / "frontend-reference/apps/web/package.json").read_text()
    assert 'APP_VERSION = "4.6.0"' in main
    assert '"version": "4.6.0"' in package
