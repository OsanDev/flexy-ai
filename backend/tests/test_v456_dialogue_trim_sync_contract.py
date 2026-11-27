from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_dialogue_trim_sync_remaps_dialogue_audio_and_keeps_music_untouched():
    source = (ROOT / "frontend-reference/apps/web/src/lib/dialogueTrimSync.ts").read_text()
    assert "synchronizeDialogueAfterTrim" in source
    assert 'clip.role !== "dialogue" || clip.mediaId !== original.mediaId' in source
    assert "sourceStart," in source
    assert "volumeKeyframes" in source


def test_caption_crossing_removed_gap_is_flagged_for_review():
    source = (ROOT / "frontend-reference/apps/web/src/lib/dialogueTrimSync.ts").read_text()
    assert "spans a removed pause" in source
    assert "text-only caption data cannot safely split its words" in source


def test_pause_trim_ui_applies_audio_and_caption_sync_in_same_history_update():
    source = (ROOT / "frontend-reference/apps/web/src/components/TimelineComposer.tsx").read_text()
    assert "synchronizeDialogueAfterTrim" in source
    assert "audioClips: nextAudioClips, captions: nextCaptions" in source
