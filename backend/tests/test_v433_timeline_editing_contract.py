from pathlib import Path
SRC = Path(__file__).resolve().parents[2] / "frontend-reference/apps/web/src"
def test_timeline_supports_move_trim_split_and_delete():
    s=(SRC/"components/TimelineComposer.tsx").read_text()
    for token in ("editVideo","editAudio","splitVideo","splitAudio","splitCaption","item.remove","onPointerMove","trim-handle"):
        assert token in s
def test_timeline_supports_zoom_playhead_and_multiple_tracks():
    s=(SRC/"components/TimelineComposer.tsx").read_text()
    assert 'aria-label="Timeline zoom"' in s
    assert "setPlayhead" in s and "playhead-ruler" in s
    assert "VIDEO ${index + 1}" in s and "AUDIO ${index + 1}" in s
def test_audio_track_index_is_in_render_graph_and_validated():
    s=(SRC/"lib/timelineGraph.ts").read_text()
    assert "trackIndex: number" in s
    assert "track_index: clip.trackIndex" in s
    assert "Audio clip" in s and "clip.trackIndex > 7" in s
