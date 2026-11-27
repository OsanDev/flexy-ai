from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / "frontend-reference" / "apps" / "web" / "src"


def test_copilot_reads_selected_clip_and_neighbor_context():
    source = (WEB / "components" / "TimelineComposer.tsx").read_text()
    assert "orderedVideo" in source
    assert "previousShot" in source
    assert "nextShot" in source
    assert "selectedAsset" in source
    assert "remainingSource" in source


def test_context_panel_explains_timeline_and_source_availability():
    source = (WEB / "components" / "TimelineComposer.tsx").read_text()
    assert 'aria-label="Selected shot context"' in source
    assert "Timeline:" in source
    assert "Track {selectedVideo.trackIndex + 1}" in source
    assert "source duration unknown" in source
    assert "Previous:" in source
    assert "Next:" in source


def test_neighbor_aware_commands_propose_relative_placements():
    source = (WEB / "components" / "TimelineComposer.tsx").read_text()
    assert "after previous|after the previous|after prior" in source
    assert "before next|before the next" in source
    assert "timelineStart: position" in source
    assert "Place selected shot after the previous shot" in source
    assert "Place selected shot before the next shot" in source


def test_duration_matching_respects_remaining_source():
    source = (WEB / "components" / "TimelineComposer.tsx").read_text()
    assert "Match the previous shot's" in source
    assert "Math.min(previousShot.duration, maxDuration)" in source
    assert "duration >= 0.1" in source


def test_context_commands_remain_review_first():
    source = (WEB / "components" / "TimelineComposer.tsx").read_text()
    assert "setClipRefinement({ clipId: selectedVideo.id, patch, summary })" in source
    assert "Apply refinement" in source
    assert "Discard" in source


def test_release_version_and_context_styles_are_current():
    styles = (WEB / "styles.css").read_text()
    assert ".copilot-context" in styles
    main = (ROOT / "backend" / "app" / "main.py").read_text()
    assert 'APP_VERSION = "4.6.0"' in main
    assert 'version="4.6.0"' in main
