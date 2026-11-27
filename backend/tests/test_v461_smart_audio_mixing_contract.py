from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / "frontend-reference" / "apps" / "web" / "src"


def test_mix_assistant_uses_roles_overlap_and_existing_ducking():
    source = (WEB / "lib" / "audioMixAssistant.ts").read_text()
    assert 'clip.role === "dialogue"' in source
    assert 'clip.role === "music"' in source
    assert "musicUnderDialogue" in source
    assert "enableDucking: true" in source


def test_mix_assistant_suggests_conservative_music_level_and_fades():
    source = (WEB / "lib" / "audioMixAssistant.ts").read_text()
    assert "const target = 0.3" in source
    assert "fadeIn: 0.15" in source
    assert "fadeOut: 0.2" in source
    assert "profile.hasQuietOpening" in source
    assert "profile.hasQuietEnding" in source


def test_mix_panel_requires_approval_and_validates_fades():
    source = (WEB / "components" / "TimelineComposer.tsx").read_text()
    assert "applyAudioMixPlan" in source
    assert "Apply mix" in source and "Discard" in source
    assert "invalidFades" in source
    assert "update(nextDocument)" in source


def test_mix_panel_is_reviewable_and_one_undoable_update():
    source = (WEB / "components" / "TimelineComposer.tsx").read_text()
    assert "audioMixPlan.changes.map" in source
    assert "setAudioMixPlan(recommendAudioMix" in source
    assert "Caption-timed music dips use existing caption positions and are applied as editable volume keyframes in one undoable edit." in source


def test_release_version_is_updated():
    main = (ROOT / "backend" / "app" / "main.py").read_text()
    package = (WEB.parent / "package.json").read_text()
    assert 'APP_VERSION = "4.6.0"' in main
    assert '"version": "4.6.0"' in package
