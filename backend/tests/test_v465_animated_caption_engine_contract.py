from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / "frontend-reference" / "apps" / "web" / "src"


def test_caption_style_supports_animation_modes_and_duration():
    source = (WEB / "lib" / "timelineGraph.ts").read_text()
    assert '"none" | "word" | "karaoke" | "pop" | "fade" | "slide"' in source
    assert "animationDuration?: number" in source
    assert 'animation: "none"' in source


def test_caption_inspector_exposes_animation_and_timing_controls():
    source = (WEB / "components" / "TimelineComposer.tsx").read_text()
    for label in ["Animation", "Word reveal", "Karaoke highlight", "Animation time (s)"]:
        assert label in source
    assert 'Math.min(2, numberValue' in source


def test_preview_uses_playhead_for_word_reveal_and_karaoke_highlight():
    source = (WEB / "components" / "PlaybackPreview.tsx").read_text()
    assert "playhead - activeCaption.start" in source
    assert 'animation === "word"' in source
    assert 'animation === "karaoke"' in source
    assert "caption-word-active" in source


def test_pop_fade_and_slide_have_motion_keyframes():
    source = (WEB / "styles.css").read_text()
    for name in ["caption-animation-pop", "caption-animation-fade", "caption-animation-slide"]:
        assert name in source
    for keyframe in ["@keyframes caption-pop", "@keyframes caption-fade", "@keyframes caption-slide"]:
        assert keyframe in source


def test_release_version_is_updated():
    main = (ROOT / "backend" / "app" / "main.py").read_text()
    package = (WEB.parent / "package.json").read_text()
    assert 'APP_VERSION = "4.6.0"' in main
    assert '"version": "4.6.0"' in package
