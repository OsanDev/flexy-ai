from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / "frontend-reference" / "apps" / "web" / "src"

def test_dialogue_cut_requires_explicit_user_action():
    source = (WEB / "components" / "TimelineComposer.tsx").read_text()
    assert 'onClick={() => applyDialogueCut(marker.at)}' in source
    assert 'disabled={!hasMatchingClip}' in source
    assert '>Split clip</button>' in source

def test_dialogue_cut_splits_matching_source_clip_without_deleting_media():
    source = (WEB / "components" / "TimelineComposer.tsx").read_text()
    assert 'clip.mediaId !== transcriptionMediaId' in source
    assert 'sourceTime - clip.sourceStart' in source
    assert 'timelineStart: clip.timelineStart + offset' in source
    assert 'update({ ...doc, videoClips: nextClips })' in source

def test_dialogue_cut_uses_existing_history_update_for_undo():
    source = (WEB / "components" / "TimelineComposer.tsx").read_text()
    update_body = source.split('const update = (next: TimelineDocument) => {', 1)[1].split('};', 1)[0]
    assert 'setHistory' in update_body
    assert 'setFuture([])' in update_body
    assert 'setDoc(next)' in update_body

def test_release_version_is_454():
    source = (ROOT / "backend" / "app" / "main.py").read_text()
    assert 'APP_VERSION = "4.6.0"' in source
    assert 'version="4.6.0"' in source
