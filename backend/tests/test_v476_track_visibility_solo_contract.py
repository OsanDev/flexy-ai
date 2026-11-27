from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
COMPONENT = ROOT / "frontend-reference/apps/web/src/components/TimelineComposer.tsx"
GRAPH = ROOT / "frontend-reference/apps/web/src/lib/timelineGraph.ts"

def test_track_visibility_and_solo_controls_are_wired():
    source = COMPONENT.read_text()
    graph = GRAPH.read_text()
    assert "toggleTrackVisibility" in source
    assert "toggleAudioTrackSolo" in source
    assert "onToggleVisibility" in source
    assert "onToggleSolo" in source
    assert "hiddenVideoTracks" in graph
    assert "hiddenAudioTracks" in graph
    assert "captionsHidden" in graph
    assert "soloAudioTrack" in graph
    assert ".filter((clip) => !(document.hiddenVideoTracks" in graph
    assert ".filter((clip) => !(document.hiddenAudioTracks" in graph
    assert "clip.trackIndex !== document.soloAudioTrack ? 0 : clip.volume" in graph
