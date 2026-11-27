from pathlib import Path
from unittest.mock import patch

import pytest

from app.rendering import RenderValidationError, _ass_color, _ass_escape_text, _captions_to_ass, validate_render_graph

ROOT = Path(__file__).resolve().parents[2]


def _validated(caption):
    media_dir = Path("/tmp/flexy-v468-caption-test")
    media_dir.mkdir(exist_ok=True)
    (media_dir / "clip.mp4").write_bytes(b"video")
    try:
        with patch("app.rendering.storage.get_media", return_value={"stored_name": "clip.mp4", "mime_type": "video/mp4"}), patch("app.rendering.storage.MEDIA_DIR", media_dir):
            return validate_render_graph({"clips": [{"media_id": "v", "duration": 3}], "captions": [caption]})
    finally:
        (media_dir / "clip.mp4").unlink(missing_ok=True)
        media_dir.rmdir()


def test_render_graph_preserves_advanced_caption_style_fields():
    result = _validated({"text": "Line one\nLine two", "start": 0.5, "duration": 2,
        "style": {"alignment": "left", "position": "top", "fontSize": 36,
            "verticalOffset": 12, "outlineColor": "#123456", "outlineWidth": 2,
            "shadowColor": "#654321", "shadowBlur": 4, "color": "#abcdef",
            "backgroundColor": "#102030cc", "bold": False}})
    style = result["captions"][0]["style"]
    assert style["alignment"] == "left" and style["position"] == "top"
    assert style["font_size"] == 36 and style["vertical_offset"] == 12
    assert style["outline_width"] == 2 and style["shadow_blur"] == 4
    assert result["captions"][0]["text"] == "Line one\nLine two"


def test_invalid_caption_style_is_rejected():
    with pytest.raises(RenderValidationError):
        _validated({"text": "Hello", "start": 0, "duration": 1, "style": {"outlineWidth": 99}})


def test_ass_export_encodes_caption_style_and_multiline_text():
    ass = _captions_to_ass([{"text": "First line\nSecond line", "start": 1.25, "duration": 2,
        "style": {"alignment": "right", "position": "top", "vertical_offset": 10,
            "font_size": 42, "color": "#ffffff", "background_color": "#000000b8",
            "outline_color": "#112233", "outline_width": 3, "shadow_color": "#445566",
            "shadow_blur": 5, "bold": True}}], 1920, 1080)
    assert "PlayResX: 1920" in ass and "Style: Caption0,Arial,42" in ass
    assert "Dialogue: 0,0:00:01.25,0:00:03.25,Caption0" in ass
    assert r"\an9\pos(1824,108)" in ass
    assert r"First line\NSecond line" in ass
    assert _ass_color("#112233") == "&H00332211&"
    assert _ass_color("#000000b8") == "&H47000000&"


def test_ass_text_escapes_override_delimiters_and_preserves_line_breaks():
    safe = _ass_escape_text("{\an7}hello\nworld")
    assert r"\{" in safe and r"\}" in safe and r"\N" in safe


def test_render_pipeline_uses_styled_ass_subtitles():
    source = (ROOT / "backend" / "app" / "rendering.py").read_text()
    assert 'with_suffix(".captions.ass")' in source
    assert '_captions_to_ass(graph["captions"], width, height)' in source
    assert "[outv]subtitles=filename=" in source
    assert ".captions.srt" not in source


def test_release_version_is_updated():
    main = (ROOT / "backend" / "app" / "main.py").read_text()
    package = (ROOT / "frontend-reference" / "apps" / "web" / "package.json").read_text()
    assert 'APP_VERSION = "4.6.0"' in main
    assert '"version": "4.6.0"' in package
