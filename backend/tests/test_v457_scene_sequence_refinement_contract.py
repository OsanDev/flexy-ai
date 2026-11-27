from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / "frontend-reference" / "apps" / "web" / "src"


def test_sequence_analyzer_groups_and_orders_clips_by_track():
    source = (WEB / "components" / "TimelineComposer.tsx").read_text()
    assert "const analyzeSceneSequence = () =>" in source
    assert "new Set(doc.videoClips.map((clip) => clip.trackIndex))" in source
    assert ".sort((a, b) => a.timelineStart - b.timelineStart)" in source


def test_short_gaps_are_proposed_for_closing():
    source = (WEB / "components" / "TimelineComposer.tsx").read_text()
    assert "gap > 0.15 && gap <= 3" in source
    assert "current.timelineStart = previousEnd" in source
    assert "Close ${gap.toFixed(1)}s gap" in source


def test_adjacent_shots_receive_transition_suggestion():
    source = (WEB / "components" / "TimelineComposer.tsx").read_text()
    assert "Math.abs(gap) <= 0.15 && current.transition === \"none\"" in source
    assert 'current.transition = "fade"' in source


def test_large_gaps_and_overlaps_are_warnings_not_auto_edits():
    source = (WEB / "components" / "TimelineComposer.tsx").read_text()
    assert "gap > 3" in source
    assert "gap < -0.15" in source
    assert "was left unchanged" in source
    assert "needs manual review" in source


def test_sequence_changes_require_preview_and_approval():
    source = (WEB / "components" / "TimelineComposer.tsx").read_text()
    assert "setSceneSequencePlan({ nextDocument, changes, warnings })" in source
    assert "Discard" in source
    assert "Apply sequence edits" in source
    assert "update(sceneSequencePlan.nextDocument)" in source


def test_sequence_panel_and_release_metadata_exist():
    source = (WEB / "components" / "TimelineComposer.tsx").read_text()
    assert 'aria-label="Scene-to-scene sequence analysis"' in source
    assert "Analyze sequence" in source
    assert ".scene-sequence-panel" in (WEB / "styles.css").read_text()
    main = (ROOT / "backend" / "app" / "main.py").read_text()
    assert 'APP_VERSION = "4.6.0"' in main
    assert 'version="4.6.0"' in main
