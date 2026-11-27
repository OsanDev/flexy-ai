from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_pause_trim_helper_preserves_handles_and_clip_identity():
    source = (ROOT / "frontend-reference/apps/web/src/lib/dialoguePauseTrim.ts").read_text()
    assert "handleSeconds = 0.12" in source
    assert "id: index === 0 ? clip.id" in source
    assert 'transition: index === 0 ? clip.transition : "none"' in source
    assert "removedSeconds" in source


def test_pause_trim_only_uses_long_pause_candidates():
    source = (ROOT / "frontend-reference/apps/web/src/lib/dialoguePauseTrim.ts").read_text()
    assert 'item.reason === "long_pause"' in source
    assert "cut.start - cursor >= 0.12" in source


def test_timeline_ui_applies_pause_trims_as_single_undoable_update():
    source = (ROOT / "frontend-reference/apps/web/src/components/TimelineComposer.tsx").read_text()
    assert "applyDialoguePauseTrims" in source
    assert "Trim reviewed long pauses" in source
    assert "update({ ...doc, videoClips: nextVideoClips, audioClips: nextAudioClips, captions: nextCaptions })" in source
    assert "synchronizeDialogueAfterTrim" in source
    assert "Use Undo to restore the previous timeline." in source
