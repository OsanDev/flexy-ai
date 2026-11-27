from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / "frontend-reference" / "apps" / "web" / "src"


def test_timeline_document_can_store_named_caption_presets():
    source = (WEB / "lib" / "timelineGraph.ts").read_text()
    assert "export type SavedCaptionPreset" in source
    assert "captionPresets?: SavedCaptionPreset[]" in source


def test_built_in_caption_preset_library_has_five_named_styles():
    source = (WEB / "components" / "TimelineComposer.tsx").read_text()
    for preset in ["Cinematic Fade", "Social Pop", "Karaoke Glow", "Minimal Slide", "Neon Reveal"]:
        assert preset in source


def test_selected_caption_can_apply_and_save_custom_presets():
    source = (WEB / "components" / "TimelineComposer.tsx").read_text()
    assert "applyCaptionStylePreset" in source
    assert "saveCaptionStylePreset" in source
    assert "captionPresets: [...(doc.captionPresets ?? [])" in source
    assert "Saved custom presets stay with this project" in source


def test_preset_library_controls_are_styled_and_accessible():
    source = (WEB / "components" / "TimelineComposer.tsx").read_text()
    styles = (WEB / "styles.css").read_text()
    assert 'aria-label="Custom caption preset name"' in source
    for selector in [".caption-preset-library", ".caption-preset-buttons", ".caption-save-preset"]:
        assert selector in styles


def test_release_version_is_updated():
    main = (ROOT / "backend" / "app" / "main.py").read_text()
    package = (WEB.parent / "package.json").read_text()
    assert 'APP_VERSION = "4.6.0"' in main
    assert '"version": "4.6.0"' in package
