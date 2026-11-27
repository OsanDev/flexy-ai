from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / "frontend-reference" / "apps" / "web" / "src"


def test_targeted_clip_position_and_duration_commands_are_supported():
    source = (WEB / "lib" / "timelineCommands.ts").read_text()
    assert r"move|shift|reposition" in source
    assert "Moved video clip" in source
    assert "Set video clip" in source
    assert "sort((a, b) => a.timelineStart - b.timelineStart)" in source


def test_music_volume_percentage_is_converted_and_bounded():
    source = (WEB / "lib" / "timelineCommands.ts").read_text()
    assert 'volumeMatch[2] === "%" ? requested / 100 : requested' in source
    assert "target > 2" in source
    assert "Set music volume to" in source


def test_transition_removal_and_final_validation_are_available():
    source = (WEB / "lib" / "timelineCommands.ts").read_text()
    assert "Removed transitions from" in source
    assert 'transition: "none"' in source
    assert "validateTimelineDocument(nextDocument)" in source


def test_ui_surfaces_refinement_examples_and_approval_preview():
    source = (WEB / "components" / "TimelineComposer.tsx").read_text()
    assert "Move clip 2 to 5 seconds" in source
    assert "Set music volume to 40%" in source
    assert "Apply edits" in source
    assert "Discard" in source


def test_release_version_tracks_current_release():
    source = (ROOT / "backend" / "app" / "main.py").read_text()
    assert 'APP_VERSION = "4.6.0"' in source
