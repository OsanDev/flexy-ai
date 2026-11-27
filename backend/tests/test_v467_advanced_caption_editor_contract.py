from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / "frontend-reference" / "apps" / "web" / "src"


def test_caption_style_schema_has_layout_and_effect_controls():
    source = (WEB / "lib" / "timelineGraph.ts").read_text()
    for field in ["alignment?:", "outlineColor?:", "outlineWidth?:", "shadowColor?:", "shadowBlur?:", "verticalOffset?:"]:
        assert field in source


def test_caption_text_editor_supports_multiline_text():
    source = (WEB / "components" / "TimelineComposer.tsx").read_text()
    assert "<textarea rows={3}" in source
    assert "Use Enter for a new line." in source


def test_inspector_exposes_alignment_position_outline_and_shadow():
    source = (WEB / "components" / "TimelineComposer.tsx").read_text()
    for label in ["Text alignment", "Vertical position (%)", "Outline color", "Outline width (px)", "Shadow color", "Shadow blur (px)"]:
        assert label in source


def test_preview_applies_caption_layout_and_text_effects():
    source = (WEB / "components" / "PlaybackPreview.tsx").read_text()
    for prop in ["textAlign:", "WebkitTextStroke:", "textShadow:", "verticalOffset"]:
        assert prop in source
    styles = (WEB / "styles.css").read_text()
    assert "white-space:pre-wrap" in styles


def test_release_version_is_updated():
    main = (ROOT / "backend" / "app" / "main.py").read_text()
    package = (WEB.parent / "package.json").read_text()
    assert 'APP_VERSION = "4.6.0"' in main
    assert '"version": "4.6.0"' in package
