from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "frontend-reference/apps/web/src/components/TimelineComposer.tsx"

def test_multitrack_lock_and_mute_controls_are_wired():
    source = SOURCE.read_text()
    assert "toggleTrackLock" in source
    assert "toggleAudioTrackMute" in source
    assert "locked={!!lockedTracks" in source
    assert "onToggleMute={() => toggleAudioTrackMute(index)}" in source
    assert "disabled={locked}" in source
    assert "volume: 0" in source
    assert "saved[clip.id]" in source
