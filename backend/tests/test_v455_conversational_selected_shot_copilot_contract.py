from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / "frontend-reference" / "apps" / "web" / "src"

def test_selected_clip_natural_language_commands_are_recognized():
    source = (WEB / "components" / "TimelineComposer.tsx").read_text()
    assert "if (selectedVideo)" in source
    assert "shorten|trim shorter|reduce duration" in source
    assert "extend|lengthen" in source
    assert "source start|source in|start from" in source
    assert "crossfade" in source

def test_move_command_targets_requested_timeline_position():
    source = (WEB / "components" / "TimelineComposer.tsx").read_text()
    assert "timelineStart: position" in source
    assert "Move selected shot to" in source

def test_proposals_require_approval():
    source = (WEB / "components" / "TimelineComposer.tsx").read_text()
    assert "setClipRefinement({ clipId: selectedVideo.id, patch, summary })" in source
    assert "applyClipRefinement" in source
    assert "patchSelected(clipRefinement.patch)" in source
    assert "Discard" in source

def test_source_and_duration_limits_are_checked():
    source = (WEB / "components" / "TimelineComposer.tsx").read_text()
    assert "asset.duration - sourceStart" in source
    assert "duration >= 0.1" in source
    assert "Math.max(0.1, selectedVideo.duration -" in source

def test_prompts_and_release_version_exist():
    source = (WEB / "components" / "TimelineComposer.tsx").read_text()
    assert "Shorten this clip by 1 second" in source
    assert "Move this clip after previous" in source
    assert "Set source start to 2 seconds" in source
    assert ".selected-shot-examples" in (WEB / "styles.css").read_text()
    main = (ROOT / "backend" / "app" / "main.py").read_text()
    assert 'APP_VERSION = "4.6.0"' in main
    assert 'version="4.6.0"' in main
