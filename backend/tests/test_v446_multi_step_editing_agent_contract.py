from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / "frontend-reference" / "apps" / "web" / "src"


def test_planner_splits_ordered_natural_language_steps():
    source = (WEB / "lib" / "timelineCommands.ts").read_text()
    assert "function splitEditingSteps(rawCommand: string)" in source
    assert r"\s+then\s+" in source
    assert "Split \"A and B\" only when B begins with a known editing action." in source
    assert "splitEditingSteps(rawCommand)" in source


def test_planner_has_bounded_step_count_and_atomic_failure():
    source = (WEB / "lib" / "timelineCommands.ts").read_text()
    assert "steps.length > 8" in source
    assert "No steps have been applied." in source
    assert "nextDocument: cloneDocument(document)" in source


def test_each_step_receives_previous_proposed_document():
    source = (WEB / "lib" / "timelineCommands.ts").read_text()
    assert "planSingleTimelineCommand(working, steps[index])" in source
    assert "working = result.nextDocument" in source
    assert "validateTimelineDocument(working)" in source


def test_ui_describes_ordered_multi_step_approval():
    source = (WEB / "components" / "TimelineComposer.tsx").read_text()
    assert "Make it cinematic, then set music volume to 40%" in source
    assert "up to 8 ordered steps" in source
    assert "Apply edits" in source
    assert "Discard" in source


def test_release_version_is_v4426():
    source = (ROOT / "backend" / "app" / "main.py").read_text()
    assert 'APP_VERSION = "4.6.0"' in source
    assert 'version="4.6.0"' in source
