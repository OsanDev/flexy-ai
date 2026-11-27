from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "frontend-reference/apps/web/src/components/TimelineComposer.tsx"

def test_clip_copy_paste_duplicate_and_shortcuts_are_wired():
    source = SOURCE.read_text()
    assert "copySelectedClip" in source
    assert "pasteClip" in source
    assert "duplicateSelectedClip" in source
    assert "timelineStart: playhead" in source
    assert "start: playhead" in source
    assert "clip.timelineStart + clip.duration" in source
    assert "event.key.toLowerCase() === \"c\"" in source
    assert "event.key.toLowerCase() === \"v\"" in source
    assert "event.key.toLowerCase() === \"d\"" in source
    assert "Paste at playhead" in source
