from pathlib import Path
SRC = Path(__file__).resolve().parents[2] / "frontend-reference/apps/web/src"
def test_timeline_undo_redo_and_shortcuts():
    s=(SRC/"components/TimelineComposer.tsx").read_text()
    assert "const undo =" in s and "const redo =" in s
    assert 'event.key.toLowerCase() === "z"' in s
    assert 'event.key.toLowerCase() === "y"' in s
def test_frame_stepping_uses_project_frame_rate():
    s=(SRC/"components/TimelineComposer.tsx").read_text()
    assert "value + direction / doc.frameRate" in s
    assert "frameStep(-1)" in s and "frameStep(1)" in s
def test_playback_speed_controls_video_and_audio():
    s=(SRC/"components/PlaybackPreview.tsx").read_text()
    assert "playbackRate={playbackRate}" not in s
    assert "video.playbackRate = playbackRate" in s
    assert "audio.playbackRate = playbackRate" in s
    assert 'aria-label="Playback speed"' in s
def test_audio_fade_settings_are_editable_and_validated():
    c=(SRC/"components/TimelineComposer.tsx").read_text()
    g=(SRC/"lib/timelineGraph.ts").read_text()
    assert 'Fade in (s)' in c and 'Fade out (s)' in c
    assert "fadeIn: Number(audio.fadeIn)" in c
    assert "clip.fadeIn + clip.fadeOut > clip.duration" in g
def test_playback_preview_receives_speed_state():
    s=(SRC/"components/TimelineComposer.tsx").read_text()
    assert "onPlaybackRateChange={setPlaybackRate}" in s
