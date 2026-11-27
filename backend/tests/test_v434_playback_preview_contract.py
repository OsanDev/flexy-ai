from pathlib import Path
SRC = Path(__file__).resolve().parents[2] / "frontend-reference/apps/web/src"
def test_playback_preview_has_video_audio_caption_and_controls():
    s=(SRC/"components/PlaybackPreview.tsx").read_text()
    for token in ("<video","<audio","preview-caption","togglePlayback","onTimeUpdate","Preview seek"):
        assert token in s
def test_preview_uses_authenticated_media_route_and_timeline_offsets():
    s=(SRC/"components/PlaybackPreview.tsx").read_text()
    assert "/api/media/" in s
    assert "activeClip.sourceStart" in s
    assert "clip.timelineStart" in s
def test_timeline_composer_mounts_preview_with_shared_playhead():
    s=(SRC/"components/TimelineComposer.tsx").read_text()
    assert "<PlaybackPreview" in s
    assert "onPlayheadChange={setPlayhead}" in s
def test_app_labels_playback_milestone():
    s=(SRC/"App.tsx").read_text()
    assert "v4.2.34" in s and "previewing playback" in s
