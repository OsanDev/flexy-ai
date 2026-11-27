from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / "frontend-reference" / "apps" / "web" / "src"


def test_transition_analyzer_samples_both_boundary_frames():
    source = (WEB / "components" / "TimelineComposer.tsx").read_text()
    assert "const analyzeVisualTransitions = async () =>" in source
    assert "previous.sourceStart + previous.duration - 0.1" in source
    assert "current.sourceStart + 0.1" in source
    assert "mediaApi.preview(projectId, asset, timestamp)" in source


def test_visual_comparison_uses_local_frame_profiles():
    source = (WEB / "components" / "TimelineComposer.tsx").read_text()
    assert "analyzePreviewPixels(image)" in source
    assert "left.brightness" in source and "right.brightness" in source
    assert "left.contrast" in source and "right.contrast" in source
    assert "left.colorfulness" in source and "right.colorfulness" in source
    assert "left.tone === right.tone" in source


def test_visual_differences_create_cautious_transition_proposals():
    source = (WEB / "components" / "TimelineComposer.tsx").read_text()
    assert 'difference >= 22' in source
    assert 'difference >= 10' in source
    assert 'current.transition = "crossfade"' in source
    assert 'current.transition = "fade"' in source
    assert 'Math.abs(gap) > 0.15' in source


def test_frame_urls_are_revoked_after_sampling():
    source = (WEB / "components" / "TimelineComposer.tsx").read_text()
    assert "URL.revokeObjectURL(url)" in source


def test_visual_transition_changes_require_approval_and_undoable_update():
    source = (WEB / "components" / "TimelineComposer.tsx").read_text()
    assert "setVisualTransitionPlan({ nextDocument, findings, changes, warnings })" in source
    assert "Apply transitions" in source
    assert "Discard" in source
    assert "update(visualTransitionPlan.nextDocument)" in source


def test_visual_transition_panel_and_release_version_exist():
    source = (WEB / "components" / "TimelineComposer.tsx").read_text()
    assert 'aria-label="Visual transition analysis"' in source
    assert "Analyze frames" in source
    assert ".visual-transition-panel" in (WEB / "styles.css").read_text()
    main = (ROOT / "backend" / "app" / "main.py").read_text()
    assert 'APP_VERSION = "4.6.0"' in main
    assert 'version="4.6.0"' in main
