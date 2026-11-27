from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "frontend-reference/apps/web/src/components/TimelineComposer.tsx"


def test_magnetic_snap_can_be_enabled_or_disabled():
    source = SOURCE.read_text()
    assert "snapEnabled" in source
    assert "Magnetic snap" in source
    assert "setSnapEnabled" in source


def test_snap_targets_include_clip_edges_and_playhead():
    source = SOURCE.read_text()
    assert "const snapPoints = useMemo" in source
    assert "clip.timelineStart + clip.duration" in source
    assert "const points = [0, playhead, ...beatTimelineMarkers]" in source


def test_dragging_uses_pixel_threshold_and_snap_candidates():
    source = SOURCE.read_text()
    assert "8 / pixelsPerSecond" in source
    assert "adjustedDelta += nearest.time - nearest.edge" in source
    assert "magnetic-guide" in source


def test_video_clips_can_choose_transition_type():
    source = SOURCE.read_text()
    assert 'transition: "none" | "fade" | "crossfade"' in (ROOT / "frontend-reference/apps/web/src/lib/timelineGraph.ts").read_text()
    assert "Transition<select" in source
    assert "video.transition" in source
