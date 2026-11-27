from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / "frontend-reference" / "apps" / "web" / "src"


def test_caption_style_schema_and_render_graph_include_styling():
    source = (WEB / "lib" / "timelineGraph.ts").read_text()
    assert "export type CaptionStyle" in source
    assert '"classic" | "bold" | "minimal" | "neon"' in source
    assert "style: caption.style" in source


def test_caption_inspector_exposes_style_controls():
    source = (WEB / "components" / "TimelineComposer.tsx").read_text()
    for label in ["Style preset", "Position", "Font size", "Text color", "Background color", "Bold text"]:
        assert label in source


def test_playback_preview_renders_caption_style_and_position():
    source = (WEB / "components" / "PlaybackPreview.tsx").read_text()
    assert "caption-preset-" in source
    assert "caption-position-" in source
    assert "style?.fontSize" in source
    assert "style?.color" in source


def test_subtitle_studio_has_preset_specific_styles():
    source = (WEB / "styles.css").read_text()
    for preset in ["classic", "bold", "minimal", "neon"]:
        assert f".preview-caption.caption-preset-{preset}" in source


def test_release_version_is_updated():
    main = (ROOT / "backend" / "app" / "main.py").read_text()
    package = (WEB.parent / "package.json").read_text()
    assert 'APP_VERSION = "4.6.0"' in main
    assert '"version": "4.6.0"' in package
