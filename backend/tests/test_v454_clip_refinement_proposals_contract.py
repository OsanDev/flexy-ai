from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / "frontend-reference" / "apps" / "web" / "src"


def test_selected_video_inspector_offers_refinement_actions():
    source = (WEB / "components" / "TimelineComposer.tsx").read_text()
    assert "Quick AI editing suggestions" in source
    assert "Shorten 0.5s" in source
    assert "Extend 0.5s" in source
    assert "Move to end" in source
    assert "Change transition" in source


def test_refinements_are_proposals_before_application():
    source = (WEB / "components" / "TimelineComposer.tsx").read_text()
    assert "proposeClipRefinement" in source
    assert "Preview: {clipRefinement.summary}" in source
    assert "Discard" in source
    assert "Apply refinement" in source
    assert "patchSelected(clipRefinement.patch)" in source


def test_shortening_keeps_minimum_clip_duration():
    source = (WEB / "components" / "TimelineComposer.tsx").read_text()
    assert "Math.max(0.1, selectedVideo.duration - 0.5)" in source


def test_extension_respects_known_source_duration():
    source = (WEB / "components" / "TimelineComposer.tsx").read_text()
    assert "asset.duration - selectedVideo.sourceStart" in source
    assert "Math.min(selectedVideo.duration + 0.5, maxDuration)" in source


def test_move_and_transition_proposals_use_supported_values():
    source = (WEB / "components" / "TimelineComposer.tsx").read_text()
    assert "getTimelineDuration(doc)" in source
    assert '["none", "fade", "crossfade"] as const' in source


def test_refinement_ui_is_styled_and_release_version_is_current():
    styles = (WEB / "styles.css").read_text()
    assert ".clip-refinement" in styles
    source = (ROOT / "backend" / "app" / "main.py").read_text()
    assert 'APP_VERSION = "4.6.0"' in source
    assert 'version="4.6.0"' in source
