from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / "frontend-reference" / "apps" / "web" / "src"


def test_visual_inspector_exposes_explicit_recommendation_action():
    source = (WEB / "components" / "VisualMediaInspector.tsx").read_text()
    assert "onCreateEditPlan?: (instruction: string) => void" in source
    assert "Ask AI Director for edit recommendations" in source
    assert "onCreateEditPlan(" in source


def test_recommendation_prompt_uses_scene_evidence_and_scores():
    source = (WEB / "components" / "VisualMediaInspector.tsx").read_text()
    assert "rankShots(storyboards[asset.id], { visualWeight })" in source
    assert "shot.timestamp.toFixed(1)" in source
    assert "shot.score}/100" in source
    assert "shot.description" in source
    assert "shot.objects.join" in source
    assert "shot.actions.join" in source
    assert "shot.editing_notes.join" in source


def test_recommendation_prompt_requests_reviewable_edit_ideas():
    source = (WEB / "components" / "VisualMediaInspector.tsx").read_text()
    assert "strong opening" in source
    assert "coherent sequence" in source
    assert "shortening" in source
    assert "transitions only where justified" in source
    assert "do not treat the score as visual quality" in source
    assert "do not claim any edits have been applied" in source


def test_recommendations_reuse_ai_director_approval_flow():
    source = (WEB / "components" / "TimelineComposer.tsx").read_text()
    assert "onCreateEditPlan={(instruction)" in source
    assert "void runCommand(instruction)" in source
    assert "adaptDirectorDraftToTimeline" in source
    assert "Apply timeline" in source
    assert "Discard timeline" in source


def test_release_version_is_v4252():
    source = (ROOT / "backend" / "app" / "main.py").read_text()
    assert 'APP_VERSION = "4.6.0"' in source
    assert 'version="4.6.0"' in source
